#!/usr/bin/env python3
import sys
import re
import os


def extract_names(tex_files):
    names = set()
    for tex in tex_files:
        if not os.path.isfile(tex):
            continue
        with open(tex, "r", encoding="utf-8") as f:
            content = f.read()

        # Find all \input{tables/...} and \include{tables/...} commands
        # This pattern matches both \input and \include commands with tables/ path
        patterns = [
            r"\\input\{tables/([^}]*)\}",      # \input{tables/filename}
            r"\\include\{tables/([^}]*)\}",   # \include{tables/filename}
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # If the match ends with .tex, remove it since \input and \include don't need the extension
                if match.endswith('.tex'):
                    match = match[:-4]
                names.add(match)

    return sorted(names)


if __name__ == "__main__":
    tex_files = sys.argv[1:]
    names = extract_names(tex_files)
    print(" ".join(names))
