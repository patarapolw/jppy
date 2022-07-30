from uuid import UUID, uuid4

from fastapi import APIRouter, Response, Depends, HTTPException
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.session_verifier import SessionVerifier
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from pydantic import BaseModel
from sudachipy import dictionary, Morpheme
from regex import Regex

__all__ = ("r_tokenizer",)

r_tokenizer = APIRouter(prefix="/tokenizer")

####################
## Constants
####################

re_ja = Regex(r"[\p{Han}\p{Katakana}\p{Hiragana}]")

####################
## Models
####################


class TokenResponse(BaseModel):
    dictionary: str
    normalized: str
    reading: list[str]
    part_of_speech: str
    count: int = 1


class SessionData(BaseModel):
    exclude: list[str]
    items: dict[str, TokenResponse] = {}


class OutputResponse(BaseModel):
    result: list[TokenResponse]


class SuccessResponse(BaseModel):
    result: bool = True


####################
## Tokenizer
####################

tokenizer = dictionary.Dictionary(dict_type="full").create()


def morphome_to_pos(m: Morpheme) -> str:
    return "・".join(filter(lambda x: x != "*", m.part_of_speech()))


def morpheme_to_token(m: Morpheme) -> TokenResponse:
    return TokenResponse(
        dictionary=m.dictionary_form(),
        normalized=m.normalized_form(),
        reading=[m.reading_form()],
        part_of_speech=morphome_to_pos(m),
    )


def token_to_id(t: TokenResponse) -> str:
    return "\t".join([t.normalized, t.part_of_speech])


def is_ja(s: str) -> bool:
    return bool(re_ja.search(s))


####################
## Session
####################


cookie_params = CookieParameters()

# Uses UUID
cookie = SessionCookie(
    cookie_name="tokenizer",
    identifier="general_verifier",
    auto_error=True,
    secret_key="TEMPORARY",
    cookie_params=cookie_params,
)
backend = InMemoryBackend[UUID, SessionData]()


class BasicVerifier(SessionVerifier[UUID, SessionData]):
    def __init__(
        self,
        *,
        identifier: str,
        auto_error: bool,
        backend: InMemoryBackend[UUID, SessionData],
        auth_http_exception: HTTPException,
    ):
        self._identifier = identifier
        self._auto_error = auto_error
        self._backend = backend
        self._auth_http_exception = auth_http_exception

    @property
    def identifier(self):
        return self._identifier

    @property
    def backend(self):
        return self._backend

    @property
    def auto_error(self):
        return self._auto_error

    @property
    def auth_http_exception(self):
        return self._auth_http_exception

    def verify_session(self, model: SessionData) -> bool:
        """If the session exists, it is valid"""
        return True


verifier = BasicVerifier(
    identifier="general_verifier",
    auto_error=True,
    backend=backend,
    auth_http_exception=HTTPException(status_code=403, detail="invalid session"),
)


####################
## API
####################


@r_tokenizer.post("/", response_model=SuccessResponse)
async def create(exclude: list[TokenResponse], response: Response):
    session = uuid4()
    data = SessionData(
        exclude=list(set(map(lambda r: token_to_id(r), exclude))),
    )

    await backend.create(session, data)
    cookie.attach_to_response(response, session)

    return SuccessResponse()


@r_tokenizer.patch("/", dependencies=[Depends(cookie)], response_model=SuccessResponse)
async def tokenize(text: str, session_data: SessionData = Depends(verifier)):
    not_allowed = set(session_data.exclude)
    items = session_data.items

    for m in tokenizer.tokenize(text):
        t = morpheme_to_token(m)
        id = token_to_id(t)
        if id in not_allowed:
            continue

        v = items.get(id)
        if v:
            v.reading.append(t.reading[0])
            v.count += 1
        else:
            v = t

        items[id] = v

    session_data.items = items

    return SuccessResponse()


@r_tokenizer.post(
    "/finalize", dependencies=[Depends(cookie)], response_model=OutputResponse
)
async def finalize(
    response: Response,
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier),
):
    def sorter(v: TokenResponse) -> int:
        v.reading = list(set(v.reading))
        return -v.count

    result = list(session_data.items.values()).sort(key=sorter)

    await backend.delete(session_id)
    cookie.delete_from_response(response)

    return OutputResponse(result=result)


@r_tokenizer.delete("/", response_model=SuccessResponse)
async def destroy(response: Response, session_id: UUID = Depends(cookie)):
    await backend.delete(session_id)
    cookie.delete_from_response(response)
    return SuccessResponse()
