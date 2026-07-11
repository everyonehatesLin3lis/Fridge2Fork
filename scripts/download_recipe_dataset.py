from __future__ import annotations

import kagglehub


def main() -> None:
    path = kagglehub.dataset_download("wilmerarltstrmberg/recipe-dataset-over-2m")
    print("Path to dataset files:", path)


if __name__ == "__main__":
    main()
