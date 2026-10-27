"""Script-preserving alignment, adapted from Content Creator's local TTS plug.

All times are seconds. Deleted script words signal omissions; spelling/numeric
substitutions share the recognized span rather than triggering endless retakes.
"""
from __future__ import annotations

import difflib
import re

_STRIP = "\"'“”‘’«»()[]{}<>.,;:!?…*_"


def _key(word: str) -> str:
    return re.sub(r"[^\w]", "", word).lower()


def _number(words):
    """Recognize integer/currency normalization without accepting missing prose."""
    small = dict(zip(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(),
        range(20),
    ))
    small.update(dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10))))
    tokens = re.findall(r"\w+", " ".join(words).lower())
    if len(tokens) == 1 and tokens[0].isdigit():
        return int(tokens[0])
    current = total = 0
    seen = False
    for token in tokens:
        if token in {"and", "dollar", "dollars", "pound", "pounds", "euro", "euros"}:
            continue
        if token in small:
            current += small[token]
        elif token == "hundred":
            current = max(1, current) * 100
        elif token in {"thousand", "million"}:
            total += max(1, current) * (1000 if token == "thousand" else 1000000)
            current = 0
        else:
            return None
        seen = True
    return total + current if seen else None


def _equivalent(script, heard):
    contractions = {"dont": "donot", "doesnt": "doesnot", "didnt": "didnot", "cant": "cannot",
                    "wont": "willnot", "isnt": "isnot", "arent": "arenot", "im": "iam",
                    "youre": "youare", "theyre": "theyare", "ive": "ihave", "havent": "havenot",
                    "hasnt": "hasnot", "couldnt": "couldnot", "wouldnt": "wouldnot", "shouldnt": "shouldnot"}
    def normalized(words):
        return "".join(contractions.get(_key(word), _key(word)) for word in words)
    if normalized(script) == normalized(heard):
        return True
    number = _number(script)
    return number is not None and number == _number(heard)


def align(script: str, heard: list[dict], duration: float) -> tuple[list[dict], list[str]]:
    tokens = [t for t in script.split() if re.search(r"\w", t)]
    spans = [None] * len(tokens)
    missing = []

    def spread(start_index, end_index, start, end):
        weights = [max(1, len(_key(t))) for t in tokens[start_index:end_index]]
        total = sum(weights)
        cursor = start
        for i, weight in zip(range(start_index, end_index), weights):
            stop = cursor + max(0, end - start) * weight / total
            spans[i] = (cursor, stop)
            cursor = stop

    ops = difflib.SequenceMatcher(
        a=[_key(t) for t in tokens], b=[_key(h["word"]) for h in heard], autojunk=False,
    ).get_opcodes()
    for op, i1, i2, j1, j2 in ops:
        if op == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                spans[i] = (heard[j]["start"], heard[j]["end"])
        elif op == "replace":
            if _equivalent(tokens[i1:i2], [word["word"] for word in heard[j1:j2]]):
                spread(i1, i2, heard[j1]["start"], heard[j2 - 1]["end"])
            else:
                # Pair close ASR spelling/plural variants. Remaining script
                # words are unverified, not evidence of complete narration.
                candidates = sorted((
                    (difflib.SequenceMatcher(a=_key(tokens[i]), b=_key(heard[j]["word"])).ratio(), i, j)
                    for i in range(i1, i2) for j in range(j1, j2)
                ), reverse=True)
                used_i, used_j, pairs = set(), set(), []
                for similarity, i, j in candidates:
                    ordered = all((i - previous_i) * (j - previous_j) > 0 for previous_i, previous_j in pairs)
                    if similarity >= 0.6 and i not in used_i and j not in used_j and ordered:
                        spans[i] = (heard[j]["start"], heard[j]["end"])
                        used_i.add(i)
                        used_j.add(j)
                        pairs.append((i, j))
                missing.extend(tokens[i].strip(_STRIP) for i in range(i1, i2) if i not in used_i)
        elif op == "delete":
            missing.extend(t.strip(_STRIP) for t in tokens[i1:i2])
    i = 0
    while i < len(tokens):
        if spans[i] is not None:
            i += 1
            continue
        j = i
        while j < len(tokens) and spans[j] is None:
            j += 1
        left = spans[i - 1][1] if i else 0.0
        right = spans[j][0] if j < len(tokens) else duration
        if right - left >= 0.08 * (j - i) or (i == 0 and j == len(tokens)):
            spread(i, j, left, right)
        elif i:
            spread(i - 1, j, spans[i - 1][0], right)
        else:
            spread(i, j + 1, left, spans[j][1])
        i = j
    return [
        {"word": token.strip(_STRIP) or token,
         "start": round(max(0, min(duration, span[0])), 6),
         "end": round(max(0, min(duration, span[1])), 6)}
        for token, span in zip(tokens, spans)
    ], missing
