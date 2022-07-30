import sys
from pathlib import Path
from collections import Counter

from sudachipy import dictionary
from regex import Regex

re_ja = Regex(r"[\p{Han}\p{Katakana}\p{Hiragana}]")

tokenizer_obj = dictionary.Dictionary(dict_type="full").create()

items: list[str] = []

for t in tokenizer_obj.tokenize(Path(sys.argv[1]).read_text("utf-8")):
    if re_ja.search(t.normalized_form()):
        items.append(
            " ".join(
                [
                    t.dictionary_form(),
                    t.normalized_form(),
                    t.reading_form(),
                    "・".join(filter(lambda x: x != "*", t.part_of_speech())),
                ]
            )
        )

for k, n in Counter(items).most_common():
    print(k + "         " + str(n))
