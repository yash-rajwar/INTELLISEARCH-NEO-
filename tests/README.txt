Local isolated tests (do not connect Elasticsearch):
  .\.showcase_env\Scripts\python.exe -m unittest discover -s .\intellisearch_showcase\tests -v
For verification against your actual Elasticsearch installation, run preflight,
then the app; UI smoke-test and upload using a SMALL text PDF first.
