"""Compare isolated-stain counts with human counts from an explicit manifest.

No training, database, network or image modification is performed. Count errors
alone cannot measure detection precision/recall or validate agronomic efficacy.
"""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.image_analysis import DropletAnalyzer


def evaluate(manifest_path, analyzer=None):
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("images"), list) or not manifest["images"]:
        raise ValueError("Manifesto exige schema_version=1 e uma lista não vazia de imagens.")
    analyzer = analyzer or DropletAnalyzer()
    rows = []
    for entry in manifest["images"]:
        expected = entry.get("expected_isolated_count")
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
            raise ValueError("Cada imagem exige contagem humana inteira não negativa, sem valores de exemplo/null.")
        image = path.parent / entry["image_path"]
        if not image.is_file():
            raise ValueError(f"Imagem não encontrada: {image}")
        result = analyzer.process_image(str(image), options=entry.get("options") or {})
        predicted = result["valid_droplets"]
        error = predicted - expected
        rows.append({"image_path": entry["image_path"], "expected": expected, "predicted": predicted,
                     "signed_error": error, "absolute_error": abs(error),
                     "relative_error_percent": abs(error) / expected * 100 if expected else None,
                     "measurement_status": result["measurement_status"], "engine_version": result["engine_version"],
                     "warnings": result.get("warnings", [])})
    total = len(rows)
    return {"schema_version": 1, "evaluation_id": manifest.get("evaluation_id"), "images": rows,
            "metrics": {"evaluated_images": total,
                        "count_mae": sum(row["absolute_error"] for row in rows) / total,
                        "count_rmse": math.sqrt(sum(row["signed_error"] ** 2 for row in rows) / total),
                        "count_bias": sum(row["signed_error"] for row in rows) / total,
                        "exact_count_matches": sum(row["absolute_error"] == 0 for row in rows)},
            "limitations": ["Igualdade de contagens pode ocultar falsos positivos e negativos que se compensam.",
                            "Este relatório não mede precisão/recall por objeto nem eficácia agronômica.",
                            "Use imagens independentes da calibração e revise concordância entre anotadores."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args.manifest)
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
        print(f"Relatório salvo em {args.output}")
    else:
        print(content)


if __name__ == "__main__":
    main()
