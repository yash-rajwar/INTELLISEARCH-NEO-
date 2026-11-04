"""Allowlisted Elasticsearch operations; all legacy indexes remain strictly read-only."""
import json
import time
import requests
from urllib.parse import quote
from config import ES_URL,ES_USER,ES_PASSWORD,UP_INDEX,SOURCES

class ESFailure(RuntimeError): pass

class ES:
    def __init__(self,password=None,session=None):
        self.s=session or requests.Session()
        self.s.trust_env=False
        self.s.auth=(ES_USER, ES_PASSWORD if password is None else password)
        self.inference_id=None
        self.upload_semantic=False
    def api(self,method,path,*,payload=None,timeout=45, raw=None):
        try:
            kw={'timeout':(5,timeout)}
            if raw is not None:
                kw['data']=raw;kw['headers']={'Content-Type':'application/x-ndjson'}
            elif payload is not None:kw['json']=payload
            r=self.s.request(method,ES_URL+'/'+path.lstrip('/'),**kw)
            if r.status_code>=400:
                try: detail=r.json().get('error')
                except Exception:detail=r.text[:300]
                if isinstance(detail,dict):detail=detail.get('reason') or str(detail)[:300]
                raise ESFailure(f'Elasticsearch HTTP {r.status_code}: {str(detail)[:500]}')
            return r.json() if r.content else {}
        except requests.Timeout as e:raise ESFailure(f'Elasticsearch timed out after {timeout}s; ELSER may be busy. {e}') from e
        except requests.RequestException as e:raise ESFailure(f'Cannot connect to Elasticsearch: {e}') from e
    def exists(self,index):
        if index not in [x[0] for x in SOURCES.values()]:raise ESFailure('Unknown index')
        try:res=self.s.head(ES_URL+'/'+quote(index),timeout=(5,8));return res.status_code==200
        except requests.RequestException:return False
    def probe(self):
        root=self.api('GET','/',timeout=8)
        return root.get('version',{}).get('number','unknown')
    def counts(self):
        out={}
        for k,(idx,_) in SOURCES.items():
            try:out[k]=self.api('GET',f'{idx}/_count',timeout=10)['count'] if self.exists(idx) else 0
            except (KeyError,ESFailure):out[k]=None
        return out
    def get_inference(self):
        # Always reuse the actual local passage index's endpoint, never guess credentials or model ID.
        data=self.api('GET','books_passages_phase2e_v1/_mapping',timeout=12)
        props=data['books_passages_phase2e_v1']['mappings']['properties']
        sem=props.get('content_semantic',{})
        if sem.get('type')!='semantic_text':return None
        return sem.get('inference_id') or '.elser-2-elasticsearch'
    def make_upload_index(self):
        if self.exists(UP_INDEX):
            data=self.api('GET',UP_INDEX+'/_mapping',timeout=12)
            props=data[UP_INDEX]['mappings']['properties']
            self.upload_semantic=props.get('content_semantic',{}).get('type')=='semantic_text'
            return self.upload_semantic
        properties={
            'document_id':{'type':'keyword'},'filename':{'type':'keyword'},'title':{'type':'text'},
            'file_type':{'type':'keyword'},'content':{'type':'text'},'chunk_index':{'type':'integer'},
            'page_number':{'type':'integer'},'created_at':{'type':'date'},
        }
        inference=None
        try:inference=self.get_inference()
        except (ESFailure,KeyError,TypeError):pass
        if inference:properties['content_semantic']={'type':'semantic_text','inference_id':inference}
        try:
            self.api('PUT',UP_INDEX,payload={'mappings':{'dynamic':'strict','properties':properties}},timeout=18)
        except ESFailure:
            if not inference:raise
            # The local model can be unavailable despite a prior semantic index.
            # Never block BM25 uploads because ELSER mapping setup failed.
            properties.pop('content_semantic',None)
            if not self.exists(UP_INDEX):
                self.api('PUT',UP_INDEX,payload={'mappings':{'dynamic':'strict','properties':properties}},timeout=18)
            inference=None
        self.upload_semantic=bool(inference)
        self.inference_id=inference
        return self.upload_semantic
    def bulk_upload(self,doc_id,documents,*,semantic=False):
        if not self.exists(UP_INDEX):raise ESFailure('Showcase index missing.')
        rows=[]
        for i,doc in enumerate(documents):
            if doc.get('document_id')!=doc_id:raise ESFailure('Document ID mismatch')
            val=dict(doc)
            if semantic and self.upload_semantic:val['content_semantic']=val['content']
            rows.append(json.dumps({'index':{'_index':UP_INDEX,'_id':doc_id+'_'+str(i).zfill(4)}}))
            rows.append(json.dumps(val,ensure_ascii=False))
        # Bound batch sizes to protect ELSER, avoid partial timeouts with unbounded requests.
        for start in range(0,len(rows),20):
            batch='\n'.join(rows[start:start+20])+'\n'
            is_final=start+20>=len(rows)
            endpoint='_bulk?refresh=wait_for' if is_final else '_bulk'
            res=self.api('POST',endpoint,raw=batch.encode('utf-8'),timeout=160 if semantic else 30)
            if res.get('errors'):
                faults=[x.get('index',{}).get('error') for x in res.get('items',[]) if x.get('index',{}).get('error')]
                raise ESFailure('Bulk indexing error: '+str(faults[0])[:350] if faults else 'Bulk indexing error')
    def get_hit(self,index,doc_id):
        if index not in [x[0] for x in SOURCES.values()]:raise ESFailure('Invalid index.')
        try:
            data=self.api('GET',quote(index)+'/_doc/'+quote(doc_id,safe=''),timeout=12)
        except ESFailure as exc:
            if 'HTTP 404' in str(exc):return {}
            raise
        return data.get('_source',{})
