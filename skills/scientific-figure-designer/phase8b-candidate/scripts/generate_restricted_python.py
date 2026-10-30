#!/usr/bin/env python3
"""Generate the only executable program form admitted by Phase 8B minimum."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from phase8b_runtime import Phase8BError, file_sha256, payload_sha256, read_json, validate_schema


GENERATOR_ID = "phase8b-restricted-python-generator"
GENERATOR_VERSION = "0.1.0"
SCRIPT_PATH = Path(__file__).resolve()
ALLOWED_OPERATIONS = {
    "draw_axes", "draw_raw_points", "draw_supplied_annotation", "draw_legend",
    "export_svg", "export_png", "export_plot_data", "export_session_metadata",
}


def validate_plan(plan: dict[str, Any]) -> list[dict[str, str]]:
    issues = validate_schema(plan, "bounded-program-plan.schema.json", "$.bounded_program_plan")
    if plan.get("plan_sha256") != payload_sha256(plan, "plan_sha256"):
        issues.append({"layer": "deterministic", "path": "$.bounded_program_plan.plan_sha256", "code": "plan:self_hash", "message": "bounded plan self-hash mismatch", "review_route": "deterministic", "severity": "error"})
    seen: set[str] = set()
    for index, operation in enumerate(plan.get("operations", [])):
        op_id = operation.get("operation_id")
        if op_id in seen:
            issues.append({"layer": "deterministic", "path": f"$.bounded_program_plan.operations[{index}]", "code": "plan:duplicate_operation", "message": "operation_id must be unique", "review_route": "deterministic", "severity": "error"})
        seen.add(op_id)
        if operation.get("operation") not in ALLOWED_OPERATIONS:
            issues.append({"layer": "deterministic", "path": f"$.bounded_program_plan.operations[{index}].operation", "code": "plan:operation_not_allowlisted", "message": "operation is outside the Phase 8B minimum allowlist", "review_route": "deterministic", "severity": "error"})
        if operation.get("figure_id") != plan.get("figure_id") or operation.get("panel_id") not in plan.get("panel_order", []):
            issues.append({"layer": "deterministic", "path": f"$.bounded_program_plan.operations[{index}]", "code": "mapping:figure_panel", "message": "operation does not bind the declared Figure/panel", "review_route": "deterministic", "severity": "error"})
        forbidden = {"filter", "exclude", "transform", "aggregate", "crop", "contrast", "statistic", "download", "install"}
        if forbidden & set(operation.get("parameters", {})):
            issues.append({"layer": "deterministic", "path": f"$.bounded_program_plan.operations[{index}].parameters", "code": "plan:undeclared_scientific_operation", "message": "plan contains a forbidden scientific/data-changing parameter", "review_route": "deterministic", "severity": "error"})
    if plan.get("seed_policy", {}).get("stochastic_operations") is True and plan.get("seed_policy", {}).get("seed") is None:
        issues.append({"layer": "deterministic", "path": "$.bounded_program_plan.seed_policy", "code": "plan:seed_required", "message": "stochastic operation lacks a seed", "review_route": "deterministic", "severity": "error"})
    return issues


def _program_config(plan: dict[str, Any]) -> dict[str, Any]:
    annotations: dict[str, str] = {}
    axes_operation: dict[str, Any] | None = None
    for operation in plan["operations"]:
        if operation["operation"] == "draw_axes" and axes_operation is None:
            axes_operation = operation
        if operation["operation"] == "draw_supplied_annotation":
            annotations[operation["panel_id"]] = operation["parameters"].get("symbol", "")
    if axes_operation is None:
        raise Phase8BError("bounded plan lacks draw_axes")
    first_binding = plan["input_bindings"][0]
    return {
        "generator": {"id": GENERATOR_ID, "version": GENERATOR_VERSION, "sha256": file_sha256(SCRIPT_PATH)},
        "plan": {"id": plan["plan_id"], "version": plan["schema_version"], "sha256": plan["plan_sha256"]},
        "input": {"path": first_binding["path"], "sha256": first_binding["sha256"], "variables": first_binding["variables"]},
        "axes": {
            "x_variable": axes_operation["variable_bindings"]["x"],
            "y_variable": axes_operation["variable_bindings"]["y"],
            "color_variable": axes_operation["variable_bindings"]["color"],
            "entity_variable": first_binding["variables"][0],
            "x_unit": axes_operation["parameters"]["x_unit"],
            "y_unit": axes_operation["parameters"]["y_unit"],
        },
        "output_directory": plan["output_directory"],
        "figure_id": plan["figure_id"], "panel_order": plan["panel_order"], "group_order": plan["group_order"],
        "palette": plan["palette"], "annotations": annotations, "operations": plan["operations"], "outputs": plan["outputs"],
    }


PROGRAM_TEMPLATE = '''#!/usr/bin/env python3
"""GENERATED_PHASE8B_RESTRICTED_PROGRAM: do not edit by hand."""
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from xml.sax.saxutils import escape

CONFIG = json.loads(__CONFIG_LITERAL__)

def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()

def load_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = set(CONFIG["input"]["variables"])
    if not rows or not required.issubset(rows[0]):
        raise RuntimeError("declared input variables are absent")
    return rows

def y_coordinate(value, low, high, top, bottom):
    span = high - low
    if span == 0:
        return (top + bottom) / 2
    return bottom - ((value - low) / span) * (bottom - top)

def draw_png(rows, output_path):
    width, height = 1200, 520
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    y_values = [float(row[CONFIG["axes"]["y_variable"]]) for row in rows]
    low, high = min(y_values), max(y_values)
    margin = max((high - low) * 0.1, 0.1)
    low, high = low - margin, high + margin
    panel_width = width // len(CONFIG["panel_order"])
    for panel_index, panel_id in enumerate(CONFIG["panel_order"]):
        left = panel_index * panel_width + 70
        right = (panel_index + 1) * panel_width - 35
        top, bottom = 55, height - 75
        draw.line((left, top, left, bottom), fill="black", width=2)
        draw.line((left, bottom, right, bottom), fill="black", width=2)
        draw.text((left, 20), panel_id, fill="black")
        draw.text((left + 5, top + 5), CONFIG["axes"]["y_variable"] + " (" + CONFIG["axes"]["y_unit"] + ")", fill="black")
        group_span = (right - left) / max(len(CONFIG["group_order"]), 1)
        for group_index, group in enumerate(CONFIG["group_order"]):
            x = left + group_span * (group_index + 0.5)
            draw.text((x - 20, bottom + 18), group, fill="black")
            group_rows = [row for row in rows if row[CONFIG["axes"]["x_variable"]] == group]
            for point_index, row in enumerate(group_rows):
                offset = (point_index - (len(group_rows) - 1) / 2) * 14
                y = y_coordinate(float(row[CONFIG["axes"]["y_variable"]]), low, high, top, bottom)
                color = CONFIG["palette"][group]
                draw.ellipse((x + offset - 5, y - 5, x + offset + 5, y + 5), fill=color, outline="black")
        annotation = CONFIG["annotations"].get(panel_id)
        if annotation:
            draw.text((right - 95, top + 10), annotation, fill="black")
    image.save(output_path, format="PNG")

def draw_svg(rows, output_path):
    width, height = 1200, 520
    y_values = [float(row[CONFIG["axes"]["y_variable"]]) for row in rows]
    low, high = min(y_values), max(y_values)
    margin = max((high - low) * 0.1, 0.1)
    low, high = low - margin, high + margin
    panel_width = width // len(CONFIG["panel_order"])
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>']
    for panel_index, panel_id in enumerate(CONFIG["panel_order"]):
        left = panel_index * panel_width + 70
        right = (panel_index + 1) * panel_width - 35
        top, bottom = 55, height - 75
        parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="black" stroke-width="2"/>')
        parts.append(f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="black" stroke-width="2"/>')
        parts.append(f'<text x="{left}" y="30" font-size="16">{escape(str(panel_id))}</text>')
        parts.append(f'<text x="{left + 5}" y="{top + 15}" font-size="12">{escape(CONFIG["axes"]["y_variable"] + " (" + CONFIG["axes"]["y_unit"] + ")")}</text>')
        group_span = (right - left) / max(len(CONFIG["group_order"]), 1)
        for group_index, group in enumerate(CONFIG["group_order"]):
            x = left + group_span * (group_index + 0.5)
            parts.append(f'<text x="{x - 20}" y="{bottom + 35}" font-size="13">{escape(str(group))}</text>')
            group_rows = [row for row in rows if row[CONFIG["axes"]["x_variable"]] == group]
            for point_index, row in enumerate(group_rows):
                offset = (point_index - (len(group_rows) - 1) / 2) * 14
                y = y_coordinate(float(row[CONFIG["axes"]["y_variable"]]), low, high, top, bottom)
                parts.append(f'<circle cx="{x + offset}" cy="{y}" r="5" fill="{CONFIG["palette"][group]}" stroke="black"/>')
        annotation = CONFIG["annotations"].get(panel_id)
        if annotation:
            parts.append(f'<text x="{right - 95}" y="{top + 20}" font-size="14">{escape(str(annotation))}</text>')
    parts.append('</svg>')
    output_path.write_text("\\n".join(parts) + "\\n", encoding="utf-8")

def write_plot_data(rows, output_path):
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\\t", lineterminator="\\n")
        writer.writerow(["panel_id"] + CONFIG["input"]["variables"] + ["y_unit"])
        for panel_id in CONFIG["panel_order"]:
            for row in rows:
                writer.writerow([panel_id] + [row[name] for name in CONFIG["input"]["variables"]] + [CONFIG["axes"]["y_unit"]])

def main():
    input_path = Path(CONFIG["input"]["path"]).resolve()
    output_directory = Path(CONFIG["output_directory"]).resolve()
    if file_hash(input_path) != CONFIG["input"]["sha256"]:
        raise RuntimeError("declared input hash mismatch")
    if not output_directory.is_dir() or any(output_directory.iterdir()):
        raise RuntimeError("output directory must exist and be empty")
    rows = load_rows(input_path)
    draw_png(rows, output_directory / "prototype.png")
    draw_svg(rows, output_directory / "prototype.svg")
    write_plot_data(rows, output_directory / "plot_data.tsv")
    session = {"backend": "restricted_python", "generator": CONFIG["generator"], "plan": CONFIG["plan"], "input_sha256": CONFIG["input"]["sha256"], "scientific_computation": "none", "render_status": "non_final_prototype"}
    (output_directory / "session.json").write_text(json.dumps(session, sort_keys=True, indent=2) + "\\n", encoding="utf-8")
    if file_hash(input_path) != CONFIG["input"]["sha256"]:
        raise RuntimeError("input mutated during render")

if __name__ == "__main__":
    main()
'''


def generate_program_text(plan: dict[str, Any]) -> str:
    issues = validate_plan(plan)
    if issues:
        raise Phase8BError(f"bounded program plan is invalid: {issues}")
    config_literal = repr(json.dumps(_program_config(plan), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return PROGRAM_TEMPLATE.replace("__CONFIG_LITERAL__", config_literal)


def generate_program(plan: dict[str, Any], output_path: Path) -> dict[str, str]:
    text = generate_program_text(plan)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": str(output_path.resolve()), "sha256": file_sha256(output_path),
        "generator_id": GENERATOR_ID, "generator_version": GENERATOR_VERSION,
        "generator_sha256": file_sha256(SCRIPT_PATH),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = generate_program(read_json(args.plan), args.output)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
