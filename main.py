from fastapi import FastAPI

from jppy.tokenizer import r_tokenizer

app = FastAPI()
app.add_api_route("/api", r_tokenizer)
