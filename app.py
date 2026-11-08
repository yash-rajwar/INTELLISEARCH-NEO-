"""IntelliSearch Showcase. Standalone local demo on port 5003; legacy indexes read-only."""

import csv
import hashlib
import secrets
import getpass
import io
import logging
import re
import threading
import time
import uuid
from pathlib import Path
from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
    session,
    jsonify,
)
from config import (
    HOST,
    PORT,
    ES_PASSWORD,
    BOOKS_DIR,
    LEGACY_ENABLED,
    UPLOADS,
    MAX_FILE_BYTES,
    ALLOWED,
    SOURCES,
    UP_INDEX,
    BOOK_FILES,
    BOOK_NAMES,
)
from store import (
    init_v2_db,
    save_doc,
    upload_doc,
    all_docs,
    log_query as _store_log_query,
    dashboard,
    now,
    save_insights,
    all_insights,
    add_bookmark,
    remove_bookmark,
    bookmarks,
    recent_queries,
    find_hash,
    remember_hash,
    forget_hash,
    remove_upload,
    mark_interrupted,
)
from extractors import text_pages, make_chunks
from es_client import ES, ESFailure
from search import MODES, SCOPES, search, result_limit, neighbour_hit_ids
from intelligence import classify, summarize, compare_texts, explain, evidence_reply
from longdoc import summarize_long, aligned_passages
from comparison import annotate
from parallel import run_compare
from documents import choices, read_source
from llm import enabled as llm_enabled, generate as llm_generate, status as llm_status
from askcheck import check_citations, no_term_overlap
from v2_reader import v2_docs, v2_path, v2_doc
from config import DATA, V2_INDEX, CORPUS_INDEX, settings
from bootstrap import load_secret_key, setup_logging
from badge import license_chip
from sysview import license_view, diagnostics_report
from querylog import make_query_logger

setup_logging(DATA)
log = logging.getLogger("intellisearch")

log_query = make_query_logger(_store_log_query, settings.log_queries)

app = Flask(__name__)
app.jinja_env.globals["LEGACY_ENABLED"] = LEGACY_ENABLED
app.config.update(
    MAX_CONTENT_LENGTH=MAX_FILE_BYTES + 2048,
    SECRET_KEY=load_secret_key(DATA),
)
init_v2_db()
mark_interrupted()
UPLOADS.mkdir(parents=True, exist_ok=True)
# Created at import time so "flask run" and other servers get a client too.
# ES() only builds an HTTP session; it does not contact Elasticsearch.
ES_CLIENT = ES(password=ES_PASSWORD) if ES_PASSWORD else None


@app.context_processor
def common():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(24)
    return dict(
        SCOPES=SCOPES,
        MODES=MODES,
        BOOK_NAMES=BOOK_NAMES,
        csrf_token=session["csrf_token"],
        has_local_llm=llm_enabled(),
        license_chip=license_chip(client),
    )


@app.before_request
def protect_local_forms():
    if request.method == "POST":
        token = request.form.get("csrf_token", "")
        if not token or not secrets.compare_digest(token, session.get("csrf_token", "")):
            abort(400, description="Form expired. Refresh this page and try again.")


@app.errorhandler(400)
def invalid_request(err):
    return render_template("error.html", message="Invalid or expired form. Refresh and retry."), 400


@app.errorhandler(413)
def too_large(err):
    return render_template("error.html", message="File too large (12 MB maximum)."), 413


@app.errorhandler(404)
def missing(err):
    return render_template("error.html", message="Page or document not found."), 404


def client():
    if ES_CLIENT is None:
        raise ESFailure("Elasticsearch client has not been initialized.")
    return ES_CLIENT


from search import highlight_html  # noqa: E402

app.jinja_env.filters["hl"] = highlight_html


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if response.mimetype == "text/html":
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
        )
    return response


@app.get("/")
def home():
    try:
        counts = client().counts()
        version = client().probe()
        error = ""
    except ESFailure as exc:
        counts = {k: None for k in SOURCES}
        version = "offline"
        error = str(exc)
    return render_template(
        "home.html", counts=counts, version=version, stats=dashboard(), error=error
    )


@app.get("/search")
def search_page():
    q = request.args.get("q", "").strip()[:501]
    scope = request.args.get("scope", "all")
    mode = request.args.get("mode", "keyword")
    book_id = request.args.get("book_id", "")
    doc_type = request.args.get("doc_type", "")
    if scope not in SCOPES:
        scope = "all"
    if mode not in MODES:
        mode = "keyword"
    limit = result_limit(request.args.get("n"))
    result = None
    error = ""
    if q:
        started = time.monotonic()
        try:
            result = search(client(), q, scope, mode, book_id, doc_type, size=limit)
        except (ESFailure, ValueError, KeyError) as exc:
            error = str(exc)
            log.warning("search failed (scope=%s mode=%s): %s", scope, mode, exc)
        ms = round((time.monotonic() - started) * 1000)
        log_query(
            q, scope, mode, len(result["hits"]) if result else 0, ms, "error" if error else "ok"
        )
    return render_template(
        "search.html",
        q=q,
        scope=scope,
        mode=mode,
        book_id=book_id,
        doc_type=doc_type,
        result=result,
        limit=limit,
        error=error,
    )


@app.get("/compare")
def compare():
    q = request.args.get("q", "").strip()[:501]
    scope = request.args.get("scope", "corpus")
    scope = scope if scope in SCOPES else "corpus"
    outputs = {}
    if q:
        outputs = run_compare(
            lambda mode: search(client(), q, scope, mode, size=5),
            lambda mode, hits, ms, status: log_query(q, scope, mode, hits, ms, status),
            (ESFailure, ValueError),
        )
    summary = annotate(outputs) if outputs else {}
    return render_template("compare.html", q=q, scope=scope, outputs=outputs, summary=summary)


@app.get("/library")
def library():
    return render_template(
        "library.html", docs=all_docs(), insights=all_insights(), v2_docs=v2_docs()
    )


@app.post("/upload")
def upload():
    upl = request.files.get("file")
    if not upl or not upl.filename:
        flash("Choose a PDF, DOCX, or TXT file.", "error")
        return redirect(url_for("library"))
    filename = Path(upl.filename.replace("\\", "/")).name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        flash("Only PDF, DOCX and TXT are supported.", "error")
        return redirect(url_for("library"))
    data = upl.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        flash("File exceeds the 12 MB limit.", "error")
        return redirect(url_for("library"))
    # Conservative format signatures to reject common extension-spoofing mistakes.
    if ext == ".pdf" and not data.lstrip().startswith(b"%PDF-"):
        flash("Invalid PDF file.", "error")
        return redirect(url_for("library"))
    if ext == ".docx" and not data.startswith(b"PK"):
        flash("Invalid DOCX file.", "error")
        return redirect(url_for("library"))
    if ext == ".docx":
        # Guard against compressed ZIP bombs before asking python-docx to parse the archive.
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if (
                    len(archive.infolist()) > 5000
                    or sum(x.file_size for x in archive.infolist()) > 40_000_000
                ):
                    flash("DOCX expands beyond the 40 MB parsing limit.", "error")
                    return redirect(url_for("library"))
        except (zipfile.BadZipFile, ValueError):
            flash("Invalid DOCX archive.", "error")
            return redirect(url_for("library"))
    digest = hashlib.sha256(data).hexdigest()
    earlier = find_hash(digest)
    if earlier:
        flash(
            "Not added: this file has the same content as "
            + (earlier.get("filename") or "an earlier upload")
            + ". Delete the earlier copy first if you want to upload it again.",
            "error",
        )
        return redirect(url_for("library"))
    doc_id = uuid.uuid4().hex
    target = UPLOADS / (doc_id + ext)
    enable_semantic = request.form.get("semantic") == "on"
    enable_ocr = request.form.get("ocr") == "on" and ext == ".pdf"
    save_doc(doc_id, filename, ext, len(data), status="extracting")
    remember_hash(digest, doc_id)  # a failed upload frees the hash again (see cleanup)
    threading.Thread(
        target=_process_upload,
        args=(doc_id, filename, ext, data, enable_semantic, enable_ocr),
        name="upload-" + doc_id[:8],
        daemon=True,
    ).start()
    flash(
        f"Upload started for {filename}. Indexing runs in the background; "
        "this page refreshes by itself.",
        "success",
    )
    return redirect(url_for("library"))


def _process_upload(doc_id, filename, ext, data, enable_semantic, enable_ocr):
    """Extract, chunk and index one upload. Runs in a background thread and never raises."""
    target = UPLOADS / (doc_id + ext)
    try:
        pages, page_count = text_pages(data, ext, ocr=enable_ocr)
        chunks = make_chunks(pages)
        created = now()
        documents = [
            {
                "document_id": doc_id,
                "filename": filename,
                "title": Path(filename).stem,
                "file_type": ext,
                "content": ch["content"],
                "chunk_index": i,
                "created_at": created,
                **({"page_number": ch["page_number"]} if ch["page_number"] is not None else {}),
            }
            for i, ch in enumerate(chunks)
        ]
        # Store original for native PDF page navigation and contextual previews.
        target.write_bytes(data)
        cache = DATA / "extracted"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{doc_id}.txt").write_text(
            "\n\n".join(p["text"] for p in pages), encoding="utf-8"
        )
        c = client()
        has_sem = c.make_upload_index()
        c.bulk_upload(doc_id, documents, semantic=False)  # usable keyword search comes first
        status = "indexed"
        sem = "not_requested"
        info = ""
        if enable_semantic and has_sem:
            try:
                c.bulk_upload(doc_id, documents, semantic=True)
                sem = "indexed"
            except ESFailure as exc:
                # Keep keyword search working even when ELSER is busy.
                try:
                    c.bulk_upload(doc_id, documents, semantic=False)
                except ESFailure:
                    pass
                sem = "failed"
                info = (
                    "Embedding inference unavailable; BM25 upload remains searchable. "
                    + str(exc)[:300]
                )
        elif enable_semantic:
            sem = "unavailable"
            info = "Semantic endpoint not available; indexed for BM25."
        save_doc(doc_id, filename, ext, len(data), len(chunks), page_count, status, sem, info)
        classification = classify("\n".join(x["text"] for x in pages)[:75000])
        ocr_pages = sum(1 for p in pages if p.get("ocr"))
        save_insights(doc_id, classification["category"], classification["tags"], ocr_pages)
        log.info("upload finished: %s (%d passages)", filename, len(chunks))
    except Exception as exc:  # noqa: BLE001 - a background thread must record any failure
        log.warning("upload failed for %s: %s", filename, exc)
        save_doc(doc_id, filename, ext, len(data), status="error", error=str(exc))
        _cleanup_failed_upload(doc_id, ext)


def _remove_upload_files(doc_id, ext):
    # Best effort: delete the saved original and the extracted-text cache.
    for path in (UPLOADS / (doc_id + ext), DATA / "extracted" / (doc_id + ".txt")):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("could not remove %s: %s", path, exc)


def _cleanup_failed_upload(doc_id, ext):
    # A failed upload must not leave half-indexed passages behind.
    try:
        client().delete_upload_chunks(doc_id)
    except ESFailure as exc:
        log.warning("cleanup of failed upload %s did not finish: %s", doc_id, exc)
    forget_hash(doc_id)
    _remove_upload_files(doc_id, ext)


@app.post("/delete/<doc_id>")
def delete_upload_route(doc_id):
    if not re.fullmatch(r"[a-f0-9]{32}", doc_id):
        abort(404)
    d = upload_doc(doc_id)
    if not d:
        abort(404)
    if d["status"] == "extracting":
        flash("This file is still being indexed. Wait for it to finish, then delete it.", "error")
        return redirect(url_for("library"))
    try:
        removed = client().delete_upload_chunks(doc_id)
    except ESFailure as exc:
        log.warning("delete failed for %s: %s", doc_id, exc)
        flash("Could not delete from Elasticsearch, nothing was removed: " + str(exc)[:300], "error")
        return redirect(url_for("library"))
    _remove_upload_files(doc_id, d["file_type"])
    remove_upload(doc_id)
    flash(f"Deleted {d['filename']} ({removed} passages removed).", "success")
    return redirect(url_for("library"))


@app.get("/uploaded/<doc_id>")
def uploaded(doc_id):
    if not re.fullmatch(r"[a-f0-9]{32}", doc_id):
        abort(404)
    d = upload_doc(doc_id)
    if not d:
        abort(404)
    path = UPLOADS / (doc_id + d["file_type"])
    if not path.is_file():
        abort(404)
    mime = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }[d["file_type"]]
    response = send_file(
        path, mimetype=mime, as_attachment=d["file_type"] == ".docx", download_name=d["filename"]
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/uploaded-v2/<doc_id>")
def uploaded_v2(doc_id):
    path = v2_path(doc_id)
    d = v2_doc(doc_id)
    if not path or not d:
        abort(404)
    mime = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }[d["file_type"]]
    response = send_file(
        path, mimetype=mime, as_attachment=d["file_type"] == ".docx", download_name=d["filename"]
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/book/<book_id>")
def book(book_id):
    if book_id not in BOOK_FILES:
        abort(404)
    p = BOOKS_DIR / BOOK_FILES[book_id]
    if not p.is_file():
        abort(404)
    try:
        line = int(request.args.get("line", "1"))
    except ValueError:
        line = 1
    lines = p.read_text(encoding="utf-8-sig").splitlines()
    line = max(1, min(line, len(lines)))
    first = max(1, line - 15)
    last = min(len(lines), line + 25)
    rows = [{"n": i, "text": lines[i - 1], "selected": i == line} for i in range(first, last + 1)]
    return render_template(
        "book.html",
        rows=rows,
        book_id=book_id,
        title=BOOK_NAMES[book_id],
        selected=line,
        total=len(lines),
    )


@app.get("/context/<index>/<hit_id>")
def context(index, hit_id):
    if index not in {idx for idx, _ in SOURCES.values()} or len(hit_id) > 200:
        abort(404)
    try:
        src = client().get_hit(index, hit_id)
    except ESFailure as e:
        return render_template("error.html", message=str(e)), 502
    if not src:
        abort(404)
    book_id = str(src.get("book_id") or "")
    start = src.get("start_line")
    end = src.get("end_line")
    source_lines = []
    if book_id in BOOK_FILES and isinstance(start, int):
        p = BOOKS_DIR / BOOK_FILES[book_id]
        if p.is_file():
            lines = p.read_text(encoding="utf-8-sig").splitlines()
            lo = max(1, start - 12)
            hi = min(len(lines), max(start, end if isinstance(end, int) else start) + 12)
            source_lines = [
                {
                    "n": i,
                    "text": lines[i - 1],
                    "selected": start <= i <= (end if isinstance(end, int) else start),
                }
                for i in range(lo, hi + 1)
            ]
    nearby = []
    if index in (UP_INDEX, V2_INDEX, CORPUS_INDEX) and src.get("document_id") is not None:
        for k, other_id in neighbour_hit_ids(
            index, src["document_id"], src.get("chunk_index", 0), settings.context_neighbours
        ):
            try:
                other = client().get_hit(index, other_id)
                if other:
                    nearby.append(
                        {
                            "index": k,
                            "page": other.get("page_number"),
                            "text": other.get("content", "")[:1800],
                        }
                    )
            except ESFailure:
                pass
    return render_template(
        "context.html",
        src=src,
        source_lines=source_lines,
        nearby=nearby,
        index=index,
        hit_id=hit_id,
    )


@app.get("/analytics")
def analytics():
    return render_template("analytics.html", stats=dashboard())


@app.get("/results.csv")
def export_results():
    q = request.args.get("q", "").strip()
    scope = request.args.get("scope", "all")
    mode = request.args.get("mode", "keyword")
    try:
        result = search(client(), q, scope, mode, size=50)
    except (ValueError, ESFailure) as exc:
        return render_template("error.html", message=str(exc)), 400
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    w.writerow(["rank", "title", "collection", "score", "source_link", "excerpt"])
    for h in result["hits"]:
        w.writerow([h["rank"], h["title"], h["type"], h["score"], h["source_url"], h["passage"]])
    return Response(
        "\ufeff" + buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=intellisearch_results.csv"},
    )


@app.get("/health")
def health():
    try:
        v = client().probe()
        return {"status": "ok", "elasticsearch": v, "isolated_upload_index": UP_INDEX}
    except ESFailure as e:
        return {"status": "degraded", "error": str(e)}, 503


@app.get("/warmup")
def warmup():
    """Open this before presenting: one tiny ELSER call so the first search is not slow."""
    try:
        return {"status": "ok", "elser_ms": client().warm_up()}
    except ESFailure as exc:
        return {"status": "failed", "error": str(exc)[:300]}, 503


# ---------------- V3 presentation & diagnostic tools (read-only) ----------------

DEMO_CASES = [
    {
        "id": "F1",
        "name": "Frankenstein: natural language",
        "query": "A scientist destroys an unfinished second creation",
        "scope": "passages",
        "expected": "Frankenstein, Chapter 20",
    },
    {
        "id": "S1",
        "name": "Sherlock Holmes: photograph",
        "query": "A monarch hires a detective to recover an embarrassing photograph from a clever woman",
        "scope": "passages",
        "expected": "The Adventures of Sherlock Holmes",
    },
    {
        "id": "D1",
        "name": "Dracula: castle wall",
        "query": "A traveler sees the owner of a castle crawling down its outer wall like a lizard",
        "scope": "passages",
        "expected": "Dracula",
    },
    {
        "id": "A1",
        "name": "Alice: tea party",
        "query": "A girl attends a strange tea party with a hatter and a hare",
        "scope": "passages",
        "expected": "Alice's Adventures in Wonderland",
    },
    {
        "id": "P1",
        "name": "Uploaded PDF: source page",
        "query": "blue lantern North Archive",
        "scope": "uploads",
        "expected": "V3 sample PDF, after uploading",
    },
]


def system_status():
    from ocr import available as ocr_available

    data = {
        "es_version": None,
        "es_error": None,
        "counts": {},
        "inference": {"state": "unverified"},
        "ocr": {},
        "ollama": {},
        "port": PORT,
    }
    try:
        data["es_version"] = client().probe()
        data["counts"] = client().counts()
        endpoint = client().get_inference()
        elser = client().elser_status()
        if endpoint:
            data["inference"] = {
                "state": (
                    "Semantic mapping found; ELSER deployment: "
                    + elser["state"]
                    + ". "
                    + elser["note"]
                ).strip(),
                "endpoint": endpoint,
            }
        else:
            data["inference"] = {"state": "No semantic mapping"}
        data["elser"] = elser
        try:
            data["license"] = client().license_info()
        except ESFailure as err:
            data["license"] = {"error": str(err)[:200]}
        data["corpus"] = client().corpus_status()
    except (ESFailure, KeyError, TypeError) as err:
        data["es_error"] = str(err)
    try:
        ok, detail = ocr_available()
        data["ocr"] = {"ready": ok, "detail": detail}
    except (OSError, ImportError, RuntimeError) as err:
        data["ocr"] = {"ready": False, "detail": str(err)}
    data["ollama"] = {
        "configured": llm_enabled(),
        "note": "Ollama configuration is not proof that a model is running.",
    }
    return data


@app.get("/evaluation")
def evaluation_page():
    """Show the two cited evaluation runs. Reads saved files only, so it works without Elasticsearch."""
    from evalview import load_cited_runs

    return render_template("evaluation.html", runs=load_cited_runs())


@app.get("/corpus-file/<name>")
def corpus_file(name):
    """Serve one original corpus document (PDF or TXT) from corpus/files."""
    from pathlib import Path as _Path
    from flask import abort, send_from_directory

    folder = _Path(__file__).resolve().parent / "corpus" / "files"
    suffix = _Path(name).suffix.lower()
    if name != _Path(name).name or suffix not in (".pdf", ".txt"):
        abort(404)
    if not (folder / name).is_file():
        abort(404)
    mime = "application/pdf" if suffix == ".pdf" else "text/plain; charset=utf-8"
    response = send_from_directory(folder, name, mimetype=mime, conditional=True)
    response.headers["Content-Disposition"] = 'inline; filename="%s"' % name.replace('"', "")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/system")
def system_page():
    s = system_status()
    lic = license_view(s.get("license"))
    return render_template(
        "system.html",
        status=s,
        lic=lic,
        elser=s.get("elser") or {},
        corpus=s.get("corpus") or {},
        report=diagnostics_report(s, lic),
    )


@app.get("/demo")
def demo_page():
    return render_template("demo.html", cases=DEMO_CASES if LEGACY_ENABLED else [])


@app.get("/api/status")
def status_api():
    state = system_status()
    return jsonify(state), 200 if state["es_version"] else 503


@app.get("/semantic-check")
def semantic_check():
    report = {"ok": False, "message": ""}
    try:
        r = search(
            client(),
            "A scientist destroys an unfinished second creation",
            "corpus",
            "semantic",
            size=1,
        )
        report = {
            "ok": True,
            "message": f"Semantic query completed: {len(r['hits'])} hits in {r['elapsed_ms']} ms.",
        }
    except (ESFailure, ValueError) as err:
        report = {"ok": False, "message": str(err)}
    return render_template("semantic_check.html", report=report)


@app.get("/api/semantic-test")
def api_semantic_test():
    """Used by the Test now button on /system: one small ELSER search, reported honestly."""
    try:
        r = search(
            client(),
            "A scientist destroys an unfinished second creation",
            "corpus",
            "semantic",
            size=1,
        )
    except (ESFailure, ValueError) as err:
        return jsonify(ok=False, message=str(err)[:300])
    if "fallback" in str(r.get("mode_used", "")):
        return jsonify(
            ok=False,
            message="ELSER did not answer; the search fell back to keyword. " + str(r.get("warning") or "")[:200],
        )
    return jsonify(
        ok=True,
        message=f"Semantic query completed: {len(r['hits'])} hit(s) in {r['elapsed_ms']} ms.",
    )


# ==================== IntelliSearch V3 enhancements ====================
@app.route("/ask", methods=["GET", "POST"])
def ask_documents():
    question = (request.values.get("question") or "").strip()[:500]
    scope = request.values.get("scope", "corpus")
    if scope not in SCOPES:
        scope = "corpus"
    mode = request.values.get("mode", "keyword")
    if mode not in MODES:
        mode = "keyword"
    answer = None
    evidences = []
    error = ""
    retrieval = None
    generated = False
    weak = False
    citation_report = None
    if question:
        try:
            retrieval = search(client(), question, scope, mode, size=6)
            evidences = evidence_reply(question, retrieval["hits"])
            weak = bool(retrieval["hits"]) and no_term_overlap(question, retrieval["hits"])
            if request.method == "POST" and request.form.get("use_llm") == "yes":
                if not llm_enabled():
                    raise ValueError(
                        "Configure INTELLI_V3_OLLAMA_MODEL to enable local AI answers."
                    )
                if not evidences:
                    raise ValueError("No search evidence. Try another question.")
                state = llm_status()
                if state["state"] != "ready":
                    raise ValueError(state["message"])
                if weak:
                    raise ValueError(
                        "AI answer skipped: none of the retrieved passages contain the words of "
                        "your question. Read the passages below, or rephrase the question."
                    )
                answer = llm_generate(question, [e["text"] for e in evidences])
                generated = True
                citation_report = check_citations(answer, len(evidences))
            log_query(question, scope, mode, len(retrieval["hits"]), retrieval["elapsed_ms"], "ok")
        except (ValueError, RuntimeError, ESFailure) as exc:
            error = str(exc)
    return render_template(
        "ask.html",
        question=question,
        scope=scope,
        mode=mode,
        evidences=evidences,
        retrieval=retrieval,
        answer=answer,
        generated=generated,
        weak=weak,
        citation_report=citation_report,
        error=error,
    )


@app.route("/summarize", methods=["GET", "POST"])
def summarize_document():
    ref = request.values.get("source", "")
    report = None
    generated = None
    error = ""
    if ref:
        try:
            source = read_source(ref)
            report = {
                "title": source["title"],
                "summary": summarize_long(source["text"], 6),
                "classification": classify(source["text"]),
                "source": source,
            }
            if request.method == "POST" and request.form.get("use_llm") == "yes":
                if not llm_enabled():
                    raise ValueError("Optional Ollama model not configured.")
                generated = llm_generate(
                    "Summarize this document in 6 factual bullet points; include [1] citations.",
                    [source["text"][:12500]],
                    task="source-grounded document summary",
                )
        except (ValueError, OSError, RuntimeError) as exc:
            error = str(exc)
    return render_template(
        "summarize.html",
        choices=choices(),
        ref=ref,
        report=report,
        generated=generated,
        error=error,
    )


@app.route("/doc-compare", methods=["GET", "POST"])
def document_compare():
    left = request.values.get("left", "")
    right = request.values.get("right", "")
    report = None
    generated = None
    error = ""
    if left or right:
        try:
            if not left or not right or left == right:
                raise ValueError("Choose two different documents.")
            a = read_source(left)
            b = read_source(right)
            report = {
                "a": a,
                "b": b,
                "metrics": compare_texts(a["text"], b["text"]),
                "aligned": aligned_passages(a["text"], b["text"]),
                "long": max(len(a["text"]), len(b["text"])) > 200000,
            }
            if request.method == "POST" and request.form.get("use_llm") == "yes":
                if not llm_enabled():
                    raise ValueError("Optional Ollama model not configured.")
                generated = llm_generate(
                    "Explain similarities, differences and conflicting claims, if any. Do not invent differences.",
                    [a["text"][:10500], b["text"][:10500]],
                    task="two-source comparison",
                )
        except (ValueError, OSError, RuntimeError) as exc:
            error = str(exc)
    return render_template(
        "doc_compare.html",
        choices=choices(),
        left=left,
        right=right,
        report=report,
        generated=generated,
        error=error,
    )


@app.get("/similar/<doc_id>")
def similar_documents(doc_id):
    if not re.fullmatch(r"[a-f0-9]{32}", doc_id):
        abort(404)
    d = upload_doc(doc_id)
    if not d or d["status"] != "indexed":
        abort(404)
    matches = []
    error = ""
    try:
        source = read_source("upload:" + doc_id)
        excerpt = source["text"][:3500]
        if excerpt.strip() and client().exists(UP_INDEX):
            q = {
                "size": 8,
                "_source": ["document_id", "filename", "content"],
                "collapse": {"field": "document_id"},
                "query": {
                    "bool": {
                        "must": [
                            {
                                "more_like_this": {
                                    "fields": ["content"],
                                    "like": excerpt,
                                    "min_term_freq": 1,
                                    "min_doc_freq": 1,
                                    "max_query_terms": 35,
                                }
                            }
                        ],
                        "must_not": [{"term": {"document_id": doc_id}}],
                    }
                },
            }
            response = client().api("POST", UP_INDEX + "/_search", payload=q, timeout=30)
            for row in response.get("hits", {}).get("hits", []):
                src = row.get("_source") or {}
                other_id = src.get("document_id", "")
                if re.fullmatch(r"[a-f0-9]{32}", other_id) and upload_doc(other_id):
                    matches.append(
                        {
                            "id": other_id,
                            "name": src.get("filename", "Uploaded file"),
                            "passage": src.get("content", "")[:450],
                            "score": row.get("_score"),
                        }
                    )
    except (ESFailure, ValueError, OSError) as exc:
        error = str(exc)
    return render_template("similar.html", document=d, matches=matches, error=error)


@app.get("/explain/<index>/<hit_id>")
def explain_hit(index, hit_id):
    if index not in {v[0] for v in SOURCES.values()} or len(hit_id) > 200:
        abort(404)
    q = request.args.get("q", "")[:500]
    mode = request.args.get("mode", "keyword")
    if mode not in MODES:
        mode = "keyword"
    try:
        src = client().get_hit(index, hit_id)
        if not src:
            abort(404)
        result = explain(
            q, str(src.get("content") or src.get("summary") or src.get("text") or "")[:12000], mode
        )
    except ESFailure as exc:
        return render_template("error.html", message=str(exc)), 502
    return render_template(
        "explain.html", result=result, query=q, src=src, index=index, hit_id=hit_id, mode=mode
    )


@app.get("/api/suggest")
def suggest():
    term = request.args.get("q", "").strip().lower()[:80]
    if len(term) < 2:
        return jsonify({"suggestions": []})
    suggestions = []
    for s in recent_queries(80) + (
        [
            "A scientist destroys an unfinished second creation",
            "A monarch hires a detective to recover an embarrassing photograph",
            "A girl attends a strange tea party with a hatter",
            "A mysterious ship arrives at Whitby",
            "blue lantern North Archive",
        ]
        if LEGACY_ENABLED
        else []
    ):
        if term in s.lower() and s not in suggestions:
            suggestions.append(s)
        if len(suggestions) >= 7:
            break
    return jsonify({"suggestions": suggestions})


@app.route("/bookmarks", methods=["GET", "POST"])
def saved_passages():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "remove":
            try:
                remove_bookmark(int(request.form.get("id", "0")))
            except ValueError:
                abort(400)
        elif action == "add":
            index = request.form.get("index", "")
            hit = request.form.get("hit_id", "")
            if index not in {v[0] for v in SOURCES.values()} or not hit or len(hit) > 200:
                abort(400)
            try:
                src = client().get_hit(index, hit)
                title = str(src.get("title") or src.get("filename") or "Saved passage")
                add_bookmark(index, hit, title, request.form.get("q", "")[:500])
                flash("Passage saved.", "success")
            except ESFailure as exc:
                flash(str(exc), "error")
        else:
            abort(400)
        return redirect(url_for("saved_passages"))
    return render_template("bookmarks.html", items=bookmarks(), recent=recent_queries(15))


if __name__ == "__main__":
    if ES_CLIENT is None:  # no ES_PASSWORD in .env or the environment
        ES_CLIENT = ES(password=getpass.getpass("Elasticsearch password (elastic user): "))
    try:
        print("Elasticsearch version:", ES_CLIENT.probe(), flush=True)
    except ESFailure as e:
        print("Elasticsearch unavailable:", e, flush=True)

    from netguard import check_host

    try:
        check_host(HOST, settings.allow_non_loopback)
    except ValueError as exc:
        raise SystemExit(str(exc))

    ELSER_KEEPALIVE_SECONDS = 120  # 0 means warm up once and stop

    def _keep_elser_warm():
        # ELSER scales to zero when idle and then needs a slow cold start. This warms it
        # at start-up and pings it now and then while the app runs.
        while True:
            try:
                log.info("ELSER warm-up finished in %s ms", ES_CLIENT.warm_up())
            except ESFailure as exc:
                log.warning("ELSER warm-up failed: %s", exc)
            if ELSER_KEEPALIVE_SECONDS <= 0:
                return
            time.sleep(ELSER_KEEPALIVE_SECONDS)

    threading.Thread(target=_keep_elser_warm, daemon=True).start()
    print(f"IntelliSearch V4 prototype: http://{HOST}:{PORT}", flush=True)
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
