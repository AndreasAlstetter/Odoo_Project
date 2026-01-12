# generate_endtoend_docs.py

from docs.endtoend_docs import generate_endtoend_markdown


def main() -> None:
    with open("docs/endtoend_demo.md", "w", encoding="utf-8") as f:
        generate_endtoend_markdown(f)


if __name__ == "__main__":
    main()
