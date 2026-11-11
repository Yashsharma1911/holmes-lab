"""Turn a simple script (*.src) into a VHS tape with human-like typing.

Script lines:
  output <file>        Output path
  setup                hidden cd + source .env + prompt
  $ <command>          type the command like a person, then Enter
  sleep <seconds>      visible pause (reading the output)
  hidden <command>     run a command off camera, wait for the prompt, then clear
  waitprompt <secs>    wait until the command finishes (prompt is back)
"""
import random, sys, pathlib

LAB = pathlib.Path(__file__).resolve().parent.parent
FAST = {"kubectl", "get", "pods", "-n", "shop", "make", "holmes", "ask", "logs", "-o", "wide"}
NEIGHBORS = {
    "a": "sq", "b": "vn", "c": "xv", "d": "sf", "e": "wr", "f": "dg", "g": "fh", "h": "gj",
    "i": "uo", "j": "hk", "k": "jl", "l": "k", "m": "n", "n": "bm", "o": "ip", "p": "o",
    "q": "w", "r": "et", "s": "ad", "t": "ry", "u": "yi", "v": "cb", "w": "qe", "x": "zc",
    "y": "tu", "z": "x",
}


def q(ch):
    return f"`{ch}`" if ch == '"' else f'"{ch}"'


def human(cmd, rng):
    out = [f"Sleep {rng.randint(500, 1400)}ms"]
    typos = 0
    words = cmd.split(" ")
    for wi, word in enumerate(words):
        fast = word in FAST or word.startswith("--")
        if wi and rng.random() < 0.07:
            out.append(f"Sleep {rng.randint(350, 1100)}ms")  # thinking
        for ci, ch in enumerate(word):
            base = rng.randint(35, 80) if fast else rng.randint(55, 140)
            if ch in '"|()?.,-_=/':
                base += rng.randint(40, 160)  # shift / reach keys
            if ci == 0:
                base += rng.randint(0, 60)
            low = ch.lower()
            if (typos < 2 and ci > 0 and low in NEIGHBORS and not fast
                    and rng.random() < 0.02):
                typos += 1
                wrong = rng.choice(NEIGHBORS[low])
                out.append(f"Type@{base}ms {q(wrong)}")
                extra = word[ci + 1: ci + 1 + rng.choice([0, 0, 1, 2])]
                for e in extra:
                    out.append(f"Type@{rng.randint(50, 110)}ms {q(e)}")
                out.append(f"Sleep {rng.randint(180, 450)}ms")
                out.append(f"Backspace@{rng.randint(70, 120)}ms {len(extra) + 1}")
                out.append(f"Sleep {rng.randint(60, 200)}ms")
                for e in [ch] + list(extra):
                    out.append(f"Type@{rng.randint(60, 120)}ms {q(e)}")
                # skip the chars we already retyped
                word_rest = word[ci + 1 + len(extra):]
                for r in word_rest:
                    out.append(f"Type@{rng.randint(45, 120)}ms {q(r)}")
                break
            out.append(f"Type@{base}ms {q(ch)}")
        if wi < len(words) - 1:
            out.append(f"Type@{rng.randint(70, 190)}ms \" \"")
    out.append(f"Sleep {rng.randint(300, 900)}ms")
    out.append("Enter")
    return out


def build(src):
    rng = random.Random(src.stem)
    lines = ["Source recordings/settings.tape"]
    for raw in src.read_text().splitlines():
        raw = raw.rstrip()
        if not raw or raw.startswith("#"):
            continue
        kw, _, arg = raw.partition(" ")
        if kw == "output":
            lines.insert(0, f"Output {arg}")
        elif kw == "setup":
            lines += [
                "Hide",
                f"Type \"cd '{LAB}' && source .env && export PATH=$PWD/.venv/bin:$PATH "
                "&& export PS1='%F{cyan}holmes-lab%f ❯ ' && clear\" Enter",
                "Sleep 1s",
                "Show",
            ]
        elif kw == "$":
            lines += human(arg, rng)
        elif kw == "sleep":
            lines.append(f"Sleep {arg}s")
        elif kw == "waitprompt":
            lines.append(f"Wait+Line@{arg}s /❯/")
        elif kw == "hidden":
            lines += ["Hide", f"Type `{arg}; clear` Enter", "Wait+Line@600s /❯/", "Show"]
        elif kw == "hidden-end":
            lines += ["Hide", f"Type `{arg} >/dev/null 2>&1` Enter", "Sleep 20s"]
        else:
            sys.exit(f"unknown line: {raw}")
    tape = src.with_suffix(".tape")
    tape.write_text("\n".join(lines) + "\n")
    print(tape)


for p in sys.argv[1:]:
    build(pathlib.Path(p))
