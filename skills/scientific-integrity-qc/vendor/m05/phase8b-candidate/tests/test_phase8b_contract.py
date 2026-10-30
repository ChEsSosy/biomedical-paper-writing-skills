from __future__ import annotations

import copy
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
SCRIPTS = TEST_ROOT.parent / "scripts"
for path in (TEST_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fixture_factory import build_complete_package, make_inspection, validation_kwargs  # noqa: E402
from phase8b_runtime import execution_package_hash, file_sha256, load_phase8a_validator, payload_sha256, write_json  # noqa: E402
from validate_generated_program import validate_program  # noqa: E402
from validate_phase8b_package import validate_design_revision_proposal, validate_phase8b_package  # noqa: E402
from validate_phase8b_admission import admit_phase8a  # noqa: E402


class Phase8BContractTests(unittest.TestCase):
    def build(self, **kwargs):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        context = build_complete_package(Path(holder.name), **kwargs)
        return context

    def validate(self, context):
        return validate_phase8b_package(**validation_kwargs(context))

    def codes(self, result):
        return {item["code"] for item in result["issues"]}

    def rewrite_hashed(self, path, value, hash_field):
        value[hash_field] = payload_sha256(value, hash_field)
        write_json(path, value)

    def test_positive_synthetic_execution_closes_hash_chain(self):
        context = self.build()
        result = self.validate(context)
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual(result["qc"]["maturity"], "prototype_generated_unverified")
        self.assertEqual(result["qc"]["module06_figure_qc_status"], "not_implemented")
        self.assertNotEqual(result["phase8a_figure_qc_sha256"], result["phase8b_figure_qc_sha256"])
        self.assertIn("does not prove", result["qc"]["inspection_provenance_limitation"])

    def test_positive_render_has_vector_raster_plot_data_and_session(self):
        context = self.build()
        roles = {item["role"] for item in context["render"]["outputs"]}
        self.assertEqual(roles, {"vector_prototype", "raster_prototype", "plotting_data", "session_metadata"})
        self.assertTrue(all(item["size"] > 0 for item in context["render"]["outputs"]))

    def test_positive_model_finding_routes_without_scientific_authority(self):
        context = self.build(inspection_class="model", inspection_blocker=True)
        result = self.validate(context)
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual(result["qc"]["maturity"], "blocked")
        self.assertEqual(context["inspection"]["findings"][0]["route"], "realization_correction")

    def test_positive_design_review_proposal_does_not_mutate_package(self):
        context = self.build()
        proposal = {
            "schema_name": "design_revision_proposal", "schema_version": "0.1.0",
            "proposal_id": "proposal-1", "proposal_sha256": "0" * 64, "proposal_kind": "presentation_only",
            "design_package_ref": {"design_package_id": context["documents"]["manifest"]["design_package_id"], "design_package_hash": context["documents"]["manifest"]["design_package_hash"]},
            "requested_changes": [{"field": "layout.panel_spacing", "before": "compact", "after": "moderate", "reason": "improve separation"}],
            "authority_route": "author_review_required", "mutates_admitted_package": False,
        }
        proposal["proposal_sha256"] = payload_sha256(proposal, "proposal_sha256")
        self.assertEqual(validate_design_revision_proposal(proposal), [])

    def test_negative_handwritten_program_is_rejected(self):
        context = self.build()
        context["program_path"].write_text(context["program_path"].read_text(encoding="utf-8") + "\nprint('edited')\n", encoding="utf-8")
        issues = validate_program(context["plan"], context["program_path"], context["execution_manifest"]["program"]["sha256"])
        self.assertIn("code:not_exact_generator_output", {item["code"] for item in issues})

    def test_negative_self_declared_performed_is_not_proof(self):
        context = self.build()
        inspection = copy.deepcopy(context["inspection"])
        inspection["performed"] = True
        inspection["inspection_sha256"] = payload_sha256(inspection, "inspection_sha256")
        write_json(context["inspection_path"], inspection)
        result = self.validate(context)
        self.assertIn("inspection:self_declared_not_proof", {item["code"] for item in result["issues"]})

    def test_negative_finality_decision_is_inactive(self):
        context = self.build()
        inspection = copy.deepcopy(context["inspection"])
        inspection["findings"].append({"finding_id": "bad", "severity": "info", "domain": "layout", "message": "bad authority", "route": "author_review", "decision_type": "finality_decision"})
        inspection["inspection_sha256"] = payload_sha256(inspection, "inspection_sha256")
        write_json(context["inspection_path"], inspection)
        result = self.validate(context)
        self.assertIn("authority:inactive_decision_type", {item["code"] for item in result["issues"]})

    def test_negative_model_scientific_authority_overclaim(self):
        context = self.build(inspection_class="model")
        inspection = copy.deepcopy(context["inspection"])
        inspection["assessed_domains"].append("scientific_validity")
        inspection["unassessed_domains"].remove("scientific_validity")
        inspection["inspection_sha256"] = payload_sha256(inspection, "inspection_sha256")
        write_json(context["inspection_path"], inspection)
        result = self.validate(context)
        self.assertIn("inspection:authority_overclaim", {item["code"] for item in result["issues"]})

    def test_positive_presentation_only_rerender_changes_execution_chain_not_design(self):
        first = self.build(suffix="1")
        second = self.build(suffix="2")
        self.assertEqual(first["documents"]["manifest"]["design_package_hash"], second["documents"]["manifest"]["design_package_hash"])
        self.assertNotEqual(first["plan"]["plan_sha256"], second["plan"]["plan_sha256"])
        self.assertNotEqual(first["execution_result"]["execution_result_sha256"], second["execution_result"]["execution_result_sha256"])
        self.assertNotEqual(first["render"]["render_manifest_sha256"], second["render"]["render_manifest_sha256"])

    def test_negative_maturity_below_ready_for_prototype(self):
        context = self.build()
        documents = context["factory"].load_package(context["package_root"])
        context["factory"].set_maturity(documents, "ready_for_author_review")
        context["factory"].save_package(context["package_root"], documents)
        trust_sha = context["factory"].write_external_trust_root(context["package_root"], context["trust_root_path"])
        validator = load_phase8a_validator()
        phase8a = validator.validate_figure_package(context["package_root"], trust_root_path=context["trust_root_path"], expected_trust_root_sha256=trust_sha)
        manifest = context["factory"].load_package(context["package_root"])["manifest"]
        receipt, issues = admit_phase8a(
            context["package_root"], context["trust_root_path"], trust_sha,
            manifest["design_package_hash"], phase8a["qc"]["artifact_id"],
            phase8a["qc"]["schema_version"], phase8a["qc"]["figure_qc_sha256"],
            mode="prototype_code_generation",
        )
        self.assertIsNone(receipt)
        self.assertIn("admission:maturity_below_ready_for_prototype", {item["code"] for item in issues})

    def test_negative_mutated_phase8a_package_forces_fresh_revalidation(self):
        for target in ("source", "analysis", "authority", "figure_contract"):
            with self.subTest(target=target):
                context = self.build()
                if target == "source":
                    path = context["package_root"] / "data" / "source.csv"
                    path.write_text(path.read_text(encoding="utf-8").replace("2.8", "9.8"), encoding="utf-8")
                else:
                    manifest = context["documents"]["manifest"]
                    if target == "analysis":
                        path = context["package_root"] / manifest["trust_bindings"]["trusted_analysis_outputs"]["path"]
                        value = json.loads(path.read_text(encoding="utf-8"))
                        value["records"][0]["p_value"] = 0.03
                    elif target == "authority":
                        path = context["package_root"] / manifest["trust_bindings"]["trusted_authority_inputs"]["path"]
                        value = json.loads(path.read_text(encoding="utf-8"))
                        value["records"][0]["decision_value"] = "reject"
                    else:
                        path = context["package_root"] / manifest["components"]["figure_contracts"][0]["path"]
                        value = json.loads(path.read_text(encoding="utf-8"))
                        value["intended_location"] = "Mutated Results"
                    write_json(path, value)
                self.assertIn("admission:phase8a_invalid", self.codes(self.validate(context)))

    def test_negative_fresh_design_and_qc_bindings_must_match(self):
        context = self.build()
        kwargs = validation_kwargs(context)
        kwargs["expected_design_package_hash"] = "0" * 64
        result = validate_phase8b_package(**kwargs)
        self.assertIn("admission:design_hash_mismatch", self.codes(result))
        kwargs = validation_kwargs(context)
        kwargs["expected_phase8a_figure_qc_sha256"] = "0" * 64
        result = validate_phase8b_package(**kwargs)
        self.assertIn("admission:phase8a_qc_hash_mismatch", self.codes(result))
        kwargs = validation_kwargs(context)
        kwargs["expected_phase8a_qc_artifact_id"] = "wrong-qc-id"
        result = validate_phase8b_package(**kwargs)
        self.assertIn("admission:phase8a_qc_identity_mismatch", self.codes(result))
        kwargs = validation_kwargs(context)
        kwargs["expected_phase8a_qc_schema_version"] = "9.9.9"
        result = validate_phase8b_package(**kwargs)
        self.assertIn("admission:phase8a_qc_version_mismatch", self.codes(result))

    def test_negative_caller_held_trust_root_hash_mismatch(self):
        context = self.build()
        kwargs = validation_kwargs(context)
        kwargs["expected_trust_root_sha256"] = "0" * 64
        self.assertIn("admission:phase8a_invalid", self.codes(validate_phase8b_package(**kwargs)))

    def test_negative_saved_receipt_cannot_replace_fresh_invocation(self):
        context = self.build()
        receipt = copy.deepcopy(context["receipt"])
        receipt["mode"] = "prototype_code_generation"
        self.rewrite_hashed(context["receipt_path"], receipt, "receipt_sha256")
        self.assertIn("admission:stale_or_self_declared_receipt", self.codes(self.validate(context)))

    def test_negative_receipt_validator_file_hash_is_bound(self):
        context = self.build()
        receipt = copy.deepcopy(context["receipt"])
        receipt["validator"]["file_sha256"] = "0" * 64
        self.rewrite_hashed(context["receipt_path"], receipt, "receipt_sha256")
        self.assertIn("admission:validator_file_hash", self.codes(self.validate(context)))

    def test_negative_malformed_phase8a_manifest_blocks_before_dereference(self):
        for mutation in ("missing_components", "missing_trust_bindings", "wrong_components_type"):
            with self.subTest(mutation=mutation):
                context = self.build()
                manifest_path = context["package_root"] / "design-package-manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if mutation == "missing_components":
                    manifest.pop("components")
                elif mutation == "missing_trust_bindings":
                    manifest.pop("trust_bindings")
                else:
                    manifest["components"] = []
                write_json(manifest_path, manifest)
                result = self.validate(context)
                self.assertFalse(result["valid"])
                self.assertEqual(result["validation_state"], "blocked")
                self.assertIsNone(result["qc"])
                self.assertIn("validation:dependency_chain_blocked", self.codes(result))

    def test_negative_malformed_receipt_blocks_before_qc_dereference(self):
        for mutation in ("non_object_receipt", "missing_phase8a_qc_ref"):
            with self.subTest(mutation=mutation):
                context = self.build()
                if mutation == "non_object_receipt":
                    write_json(context["receipt_path"], ["not", "an", "object"])
                else:
                    receipt = copy.deepcopy(context["receipt"])
                    receipt.pop("phase8a_qc_ref")
                    self.rewrite_hashed(context["receipt_path"], receipt, "receipt_sha256")
                result = self.validate(context)
                self.assertFalse(result["valid"])
                self.assertEqual(result["validation_state"], "blocked")
                self.assertIsNone(result["qc"])
                self.assertIn("validation:dependency_chain_blocked", self.codes(result))

    def test_negative_recipe_layer_and_source_variable_mapping_drift(self):
        context = self.build()
        plan = copy.deepcopy(context["plan"])
        plan["operations"][0]["layer_id"] = "invented-layer"
        plan["operations"][1]["variable_bindings"]["y"] = "invented_response"
        self.rewrite_hashed(context["plan_path"], plan, "plan_sha256")
        codes = self.codes(self.validate(context))
        self.assertIn("mapping:recipe_layer", codes)
        self.assertIn("mapping:source_variable", codes)

    def test_negative_hidden_filter_transform_aggregation_or_statistic(self):
        context = self.build()
        plan = copy.deepcopy(context["plan"])
        plan["operations"][0]["parameters"]["filter"] = "preferred rows"
        plan["operations"][1]["parameters"]["statistic"] = "new p value"
        self.rewrite_hashed(context["plan_path"], plan, "plan_sha256")
        self.assertIn("plan:undeclared_scientific_operation", self.codes(self.validate(context)))

    def test_negative_group_palette_and_annotation_drift(self):
        context = self.build()
        plan = copy.deepcopy(context["plan"])
        plan["group_order"] = list(reversed(plan["group_order"]))
        plan["palette"]["control"] = "#000000"
        annotation = next(item for item in plan["operations"] if item["operation"] == "draw_supplied_annotation")
        annotation["parameters"]["symbol"] = "p=0.0001"
        self.rewrite_hashed(context["plan_path"], plan, "plan_sha256")
        codes = self.codes(self.validate(context))
        self.assertIn("mapping:group_order_drift", codes)
        self.assertIn("mapping:palette_drift", codes)
        self.assertIn("mapping:statistical_annotation_drift", codes)

    def test_negative_unsafe_ast_families_are_rejected(self):
        context = self.build()
        original = context["program_path"].read_text(encoding="utf-8")
        cases = {
            "eval": "\neval('1+1')\n",
            "dynamic_import": "\n__import__('os')\n",
            "subprocess": "\nimport subprocess\n",
            "socket": "\nimport socket\n",
            "installer": "\nimport pip\n",
            "filesystem_discovery": "\nimport os\nos.walk('.')\n",
        }
        for case_id, suffix in cases.items():
            with self.subTest(case_id=case_id):
                context["program_path"].write_text(original + suffix, encoding="utf-8")
                codes = {item["code"] for item in validate_program(context["plan"], context["program_path"], context["execution_manifest"]["program"]["sha256"])}
                self.assertTrue({"code:prohibited_name", "code:import_not_allowlisted"} & codes)

    def test_negative_stochastic_operation_requires_seed(self):
        context = self.build()
        plan = copy.deepcopy(context["plan"])
        plan["seed_policy"] = {"stochastic_operations": True, "seed": None}
        self.rewrite_hashed(context["plan_path"], plan, "plan_sha256")
        self.assertIn("plan:seed_required", self.codes(self.validate(context)))

    def test_negative_write_scope_escape_is_rejected(self):
        context = self.build()
        manifest = copy.deepcopy(context["execution_manifest"])
        manifest["output_directory"] = "D:\\phase8b-outside-scope"
        manifest["execution_package_hash"] = execution_package_hash(manifest)
        self.rewrite_hashed(context["execution_manifest_path"], manifest, "execution_manifest_sha256")
        self.assertIn("execution:write_scope_escape", self.codes(self.validate(context)))

    def test_negative_static_or_syntax_check_is_not_execution_success(self):
        context = self.build()
        context["program_path"].write_text("def broken(:\n", encoding="utf-8")
        self.assertIn("code:syntax", self.codes(self.validate(context)))

    def test_negative_backend_is_not_silently_substituted(self):
        context = self.build()
        profile = copy.deepcopy(context["profile"])
        profile["backend"] = "figureya"
        self.rewrite_hashed(context["profile_path"], profile, "profile_sha256")
        self.assertIn("backend:unsupported", self.codes(self.validate(context)))

    def test_negative_model_profile_or_runtime_drift_requires_fresh_probe(self):
        context = self.build()
        profile = copy.deepcopy(context["profile"])
        profile["python_version"] = "model-asserted-version"
        self.rewrite_hashed(context["profile_path"], profile, "profile_sha256")
        self.assertIn("backend:fresh_probe_mismatch", self.codes(self.validate(context)))

    def test_negative_execution_authorization_must_be_external(self):
        context = self.build()
        internal = context["execution_root"] / "self-authorization.json"
        write_json(internal, context["authorization"])
        kwargs = validation_kwargs(context)
        kwargs["authorization_path"] = internal
        kwargs["expected_authorization_file_sha256"] = file_sha256(internal)
        self.assertIn("authorization:not_external", self.codes(validate_phase8b_package(**kwargs)))

    def test_negative_authorization_exact_program_and_execution_binding(self):
        context = self.build()
        authorization = copy.deepcopy(context["authorization"])
        authorization["program_sha256"] = "0" * 64
        authorization["execution_package_hash"] = "f" * 64
        self.rewrite_hashed(context["authorization_path"], authorization, "authorization_sha256")
        kwargs = validation_kwargs(context)
        kwargs["expected_authorization_file_sha256"] = file_sha256(context["authorization_path"])
        codes = self.codes(validate_phase8b_package(**kwargs))
        self.assertIn("authorization:program_mismatch", codes)
        self.assertIn("authorization:execution_package_mismatch", codes)

    def test_negative_program_command_drift(self):
        context = self.build()
        manifest = copy.deepcopy(context["execution_manifest"])
        manifest["command"] = [context["profile"]["executable_path"], "-B", "wrong-program.py"]
        manifest["execution_package_hash"] = execution_package_hash(manifest)
        self.rewrite_hashed(context["execution_manifest_path"], manifest, "execution_manifest_sha256")
        self.assertIn("execution:command_mismatch", self.codes(self.validate(context)))

    def test_negative_nonzero_or_failed_execution_is_not_success(self):
        context = self.build()
        result = copy.deepcopy(context["execution_result"])
        result["status"] = "failed"
        result["exit_code"] = 7
        result["self_certified_success"] = True
        self.rewrite_hashed(context["execution_result_path"], result, "execution_result_sha256")
        codes = self.codes(self.validate(context))
        self.assertIn("execution:not_successful", codes)
        self.assertIn("schema:additionalProperties", codes)

    def test_negative_missing_zero_byte_partial_or_undeclared_output(self):
        for mode in ("zero", "partial", "undeclared"):
            with self.subTest(mode=mode):
                context = self.build()
                png = Path(next(item["path"] for item in context["execution_result"]["outputs"] if item["format"] == "png"))
                if mode == "zero":
                    png.write_bytes(b"")
                elif mode == "partial":
                    png.write_bytes(b"partial")
                else:
                    (png.parent / "undeclared.txt").write_text("not authorized", encoding="utf-8")
                codes = self.codes(self.validate(context))
                self.assertTrue({"execution:output_identity", "execution:undeclared_or_missing_output"} & codes)

    def test_negative_prior_result_cannot_be_reused_after_output_mutation(self):
        context = self.build()
        svg = Path(next(item["path"] for item in context["execution_result"]["outputs"] if item["format"] == "svg"))
        svg.write_text(svg.read_text(encoding="utf-8") + "<!-- mutated -->\n", encoding="utf-8")
        self.assertIn("execution:output_identity", self.codes(self.validate(context)))

    def test_negative_render_metadata_hash_dimension_format_and_panel_drift(self):
        context = self.build()
        render = copy.deepcopy(context["render"])
        render["outputs"][0]["metadata"]["width"] = 999
        render["outputs"][0]["panel_ids"] = ["panel-a"]
        self.rewrite_hashed(context["render_path"], render, "render_manifest_sha256")
        codes = self.codes(self.validate(context))
        self.assertIn("render:fresh_metadata_mismatch", codes)
        self.assertIn("render:output_binding", codes)

    def test_negative_inspection_must_bind_exact_hashes_and_domains(self):
        context = self.build()
        inspection = copy.deepcopy(context["inspection"])
        inspection["inspected_outputs"][0]["sha256"] = "0" * 64
        inspection["unassessed_domains"] = []
        self.rewrite_hashed(context["inspection_path"], inspection, "inspection_sha256")
        codes = self.codes(self.validate(context))
        self.assertIn("inspection:output_binding", codes)
        self.assertIn("schema:minItems", codes)

    def test_negative_author_only_decision_wrong_role_reject_or_stale(self):
        context = self.build()
        inspection = copy.deepcopy(context["inspection"])
        inspection["findings"].append({
            "finding_id": "authority-injection", "severity": "info", "domain": "layout", "message": "invalid decision", "route": "author_review",
            "decision_type": "layout_decision", "decision_producer_role": "model", "decision_value": "reject", "authorization_state": "pending",
        })
        self.rewrite_hashed(context["inspection_path"], inspection, "inspection_sha256")
        codes = self.codes(self.validate(context))
        self.assertIn("authority:wrong_role", codes)
        self.assertIn("authority:reject_cannot_advance", codes)
        self.assertIn("authority:state_not_accepted", codes)

    def test_negative_self_promotion_and_module06_claim(self):
        context = self.build()
        inspection = copy.deepcopy(context["inspection"])
        inspection["maturity"] = "author_approved_final"
        inspection["module06_figure_qc_status"] = "passed"
        self.rewrite_hashed(context["inspection_path"], inspection, "inspection_sha256")
        codes = self.codes(self.validate(context))
        self.assertIn("maturity:self_promotion", codes)
        self.assertIn("qc:module06_figure_extension_absent", codes)

    def test_negative_scientific_change_request_cannot_supply_after_value(self):
        context = self.build()
        proposal = {
            "schema_name": "design_revision_proposal", "schema_version": "0.1.0", "proposal_id": "scientific-request-1", "proposal_sha256": "0" * 64,
            "proposal_kind": "scientific_change_request", "design_package_ref": {"design_package_id": context["documents"]["manifest"]["design_package_id"], "design_package_hash": context["documents"]["manifest"]["design_package_hash"]},
            "requested_changes": [{"field": "statistics.p_value", "before": "p=0.04", "after": "p=0.01", "reason": "model preference"}],
            "authority_route": "phase8a_revalidation_required", "mutates_admitted_package": False,
        }
        proposal["proposal_sha256"] = payload_sha256(proposal, "proposal_sha256")
        self.assertIn("proposal:scientific_after_value_forbidden", {item["code"] for item in validate_design_revision_proposal(proposal)})

    def test_negative_non_circular_self_and_upstream_hashes(self):
        context = self.build()
        result = copy.deepcopy(context["execution_result"])
        result["execution_result_sha256"] = context["render"]["render_manifest_sha256"]
        write_json(context["execution_result_path"], result)
        render = copy.deepcopy(context["render"])
        render["execution_ref"]["sha256"] = "f" * 64
        write_json(context["render_path"], render)
        codes = self.codes(self.validate(context))
        self.assertIn("execution:result_hash", codes)
        self.assertIn("render:self_hash", codes)
        self.assertIn("render:execution_binding", codes)

    def test_negative_matrix_has_unique_exact_executable_bindings(self):
        matrix_path = TEST_ROOT / "fixtures" / "negative-cases.json"
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        case_ids = [item["case_id"] for item in matrix["cases"]]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertTrue(all(case_id.startswith("P8B-") for case_id in case_ids))
        for item in matrix["cases"]:
            with self.subTest(case_id=item["case_id"]):
                method = getattr(self, item["test_binding"], None)
                self.assertTrue(callable(method), item)
                source = inspect.getsource(method)
                self.assertIn(item["expected_issue_code"], source, item)


if __name__ == "__main__":
    unittest.main()
