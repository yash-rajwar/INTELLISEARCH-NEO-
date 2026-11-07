"""IntelliSearch Showcase. Standalone local demo on port 5003; legacy indexes read-only."""

import csv
import secrets
import getpass
import io
import os
import re
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
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
from werkzeug.exceptions import RequestEntityTooLarge
from config import (
    HOST,
    PORT,
    ES_PASSWORD,
    ROOT,
    PROJECT,
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
    log_query,
    dashboard,
    now,
    save_insights,
    all_insights,
    get_insights,
    add_bookmark,
    remove_bookmark,
    bookmarks,
    recent_queries,
)
from extractors import text_pages, make_chunks
from es_client import ES, ESFailure
from search import MODES, SCOPES, search
from intelligence import classify, summarize, compare_texts, explain, evidence_reply
from documents import choices, read_source
from llm import enabled as llm_enabled, generate as llm_generate
from v2_reader import v2_docs, v2_path, v2_doc
from config import DATA, V2_INDEX, PORT

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=MAX_FILE_BYTES + 2048,
    SECRET_KEY=os.environ.get("INTELLI_SECRET_KEY") or uuid.uuid4().hex,
)
init_v2_db()
UPLOADS.mkdir(parents=True, exist_ok=True)
ES_CLIENT = None


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
    result = None
    error = ""
    if q:
        started = time.monotonic()
        try:
            result = search(client(), q, scope, mode, book_id, doc_type)
        except (ESFailure, ValueError, KeyError) as exc:
            error = str(exc)
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
        error=error,
    )


@app.get("/compare")
def compare():
    q = request.args.get("q", "").strip()[:501]
    scope = request.args.get("scope", "passages")
    scope = scope if scope in SCOPES else "passages"
    outputs = {}
    if q:
        inference_timed_out = False
        for mode in ("keyword", "semantic", "hybrid", "weighted"):
            if inference_timed_out and mode in ("hybrid", "weighted"):
                outputs[mode] = {
                    "result": None,
                    "error": "Skipped to avoid repeated ELSER timeouts. BM25 comparison is still available.",
                }
                continue
            try:
                outputs[mode] = {"result": search(client(), q, scope, mode, size=5), "error": ""}
                log_query(
                    q,
                    scope,
                    mode,
                    len(outputs[mode]["result"]["hits"]),
                    outputs[mode]["result"]["elapsed_ms"],
                    "ok",
                )
            except (ESFailure, ValueError) as exc:
                outputs[mode] = {"result": None, "error": str(exc)}
                if mode == "semantic" and ("timed out" in str(exc).lower() or "408" in str(exc)):
                    inference_timed_out = True
                log_query(q, scope, mode, 0, 0, "error")
    return render_template("compare.html", q=q, scope=scope, outputs=outputs)


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
    doc_id = uuid.uuid4().hex
    target = UPLOADS / (doc_id + ext)
    enable_semantic = request.form.get("semantic") == "on"
    enable_ocr = request.form.get("ocr") == "on" and ext == ".pdf"
    save_doc(doc_id, filename, ext, len(data), status="extracting")
    try:
        pages, page_count = text_pages(data, ext, ocr=enable_ocr)
        chunks = make_chunks(pages)
        truncated = sum(len(p["text"]) for p in pages) > 270_000 or len(chunks) >= 120
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
        c.bulk_upload(
            doc_id, documents, semantic=False
        )  # Always secure usable lexical baseline first.
        status = "indexed"
        sem = "not_requested"
        info = ""
        if enable_semantic and has_sem:
            try:
                c.bulk_upload(doc_id, documents, semantic=True)
                sem = "indexed"
            except ESFailure as exc:
                # Preserve lexical retrieval even when ELSER inference is busy.
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
        if truncated:
            info += " Indexing was capped at 120 chunks / 270,000 text characters; not all content may be searchable."
        flash(
            f"Indexed {len(chunks)} passages from {filename}. Classification: {classification['category']}."
            + " "
            + info,
            "success",
        )
    except (ValueError, RuntimeError, OSError, ESFailure, KeyError, ImportError) as exc:
        save_doc(doc_id, filename, ext, len(data), status="error", error=str(exc))
        flash("Upload could not be indexed: " + str(exc)[:450], "error")
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
    p = PROJECT / "clean_books" / BOOK_FILES[book_id]
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
        p = PROJECT / "clean_books" / BOOK_FILES[book_id]
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
    if index in (UP_INDEX, V2_INDEX) and src.get("document_id") is not None:
        n = src.get("chunk_index", 0)
        for k in (n - 1, n + 1):
            if k >= 0:
                try:
                    other = client().get_hit(index, src["document_id"] + "_" + str(k).zfill(4))
                    if other:
                        nearby.append({"index": k, "text": other.get("content", "")[:1800]})
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
        if endpoint:
            data["inference"] = {
                "state": "Mapping configured; live inference untested",
                "endpoint": endpoint,
            }
        else:
            data["inference"] = {"state": "No semantic mapping"}
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


@app.get("/system")
def system_page():
    return render_template("system.html", status=system_status())


@app.get("/demo")
def demo_page():
    return render_template("demo.html", cases=DEMO_CASES)


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
            "passages",
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


# ==================== IntelliSearch V3 enhancements ====================
@app.route("/ask", methods=["GET", "POST"])
def ask_documents():
    question = (request.values.get("question") or "").strip()[:500]
    scope = request.values.get("scope", "passages")
    if scope not in SCOPES:
        scope = "passages"
    mode = request.values.get("mode", "keyword")
    if mode not in MODES:
        mode = "keyword"
    answer = None
    evidences = []
    error = ""
    retrieval = None
    generated = False
    if question:
        try:
            retrieval = search(client(), question, scope, mode, size=6)
            evidences = evidence_reply(question, retrieval["hits"])
            if request.method == "POST" and request.form.get("use_llm") == "yes":
                if not llm_enabled():
                    raise ValueError(
                        "Configure INTELLI_V3_OLLAMA_MODEL to enable local AI answers."
                    )
                if not evidences:
                    raise ValueError("No search evidence. Try another question.")
                answer = llm_generate(question, [e["text"] for e in evidences])
                generated = True
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
                "summary": summarize(source["text"], 6),
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
            report = {"a": a, "b": b, "metrics": compare_texts(a["text"], b["text"])}
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
    for s in recent_queries(80) + [
        "A scientist destroys an unfinished second creation",
        "A monarch hires a detective to recover an embarrassing photograph",
        "A girl attends a strange tea party with a hatter",
        "A mysterious ship arrives at Whitby",
        "blue lantern North Archive",
    ]:
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
    from config import ES_URL

    password = ES_PASSWORD or getpass.getpass("Elasticsearch password (elastic user): ")
    ES_CLIENT = ES(password=password)
    try:
        print("Elasticsearch version:", ES_CLIENT.probe(), flush=True)
    except ESFailure as e:
        print("Elasticsearch unavailable:", e, flush=True)
    print("V3 showcase: http://127.0.0.1:5003 | original, V1 and V2 unchanged", flush=True)
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
