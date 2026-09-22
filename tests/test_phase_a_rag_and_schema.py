"""Test suite for Phase A: RAG chunking, 30 Arabic/English queries top-3 retrieval, and Pydantic EngineerAnswer validation."""

import pytest

from api.answer_schema import EngineerAnswer, EngineeringFinding
from knowledge.chunking import chunk_document
from knowledge.rag_engine import EngineeringDocument, EngineeringKnowledgeBase, VectorDatabase

# 30 Bilingual queries covering key electrical engineering standards
BENCHMARK_QUERIES = [
    # English queries (15)
    ("What is the maximum short-circuit current calculation according to IEC 60909?", "IEC 60909"),
    ("How to calculate peak short circuit current ip using factor kappa?", "IEC 60909"),
    ("What is the symmetrical breaking current Ib for near-to-generator faults?", "IEC 60909"),
    ("Determine the thermal equivalent short-time current Ith.", "IEC 60909"),
    ("Calculate IEEE 1584 incident energy in medium voltage switchgear.", "IEEE 1584"),
    ("What are the electrode configurations VCB, VCBB, and HCB in IEEE 1584?", "IEEE 1584"),
    ("Define the arc flash boundary for 480V motor control center.", "IEEE 1584"),
    ("How to select PPE category based on incident energy cal/cm²?", "NFPA 70E"),
    ("What are the time-current curve TCC grading margins per IEC 60255?", "IEC 60255"),
    ("Calculate standard inverse overcurrent relay operating time.", "IEC 60255"),
    ("What is the Newton-Raphson voltage convergence tolerance in IEEE 3002.7?", "IEEE 3002.7"),
    ("Evaluate line loading limits and reactive power losses in load flow.", "IEEE 3002.7"),
    ("Calculate step and touch voltage safety limits per IEEE 80.", "IEEE 80"),
    ("Determine grid resistance and ground potential rise GPR.", "IEEE 80"),
    ("What are the total harmonic distortion THD limits under IEEE 519?", "IEEE 519"),
    # Arabic queries (15)
    ("كيف يتم حساب تيار القصر الأقصى وفق معيار IEC 60909؟", "IEC 60909"),
    ("حساب تيار القمة ip ومعامل كابا kappa للشبكات الكهربائية.", "IEC 60909"),
    ("تحديد تيار القطع المتماثل Ib للقواطع الكهربائية.", "IEC 60909"),
    ("طريقة حساب الإجهاد الحراري وتيار Ith وفق المواصفة القياسية.", "IEC 60909"),
    ("حساب طاقة الوميض القوسي Arc Flash وفق معيار IEEE 1584.", "IEEE 1584"),
    ("ما هي ترتيبات الأقطاب الكهربائية VCB و VCBB في لوحات التوزيع؟", "IEEE 1584"),
    ("تحديد مسافة حدود الأمان من القوس الكهربائي Arc Flash Boundary.", "IEEE 1584"),
    ("اختيار مهمات الوقاية الشخصية PPE المناسبة لمستوى طاقة الحادث.", "NFPA 70E"),
    ("تنسيق قواطع ومرحلات الحماية ومنحنيات TCC وفق IEC 60255.", "IEC 60255"),
    ("معادلات زمن تشغيل مرحل الحماية ضد زيادة التيار القياسي العكسي.", "IEC 60255"),
    ("دراسة سريان الأحمال وتحديد هبوط الجهد وفق معيار IEEE 3002.7.", "IEEE 3002.7"),
    ("تقييم تجاوزات سعة الخطوط الكهربائية والقدرة غير الفعالة.", "IEEE 3002.7"),
    ("حساب جهد الخطوة وجهد اللمس لشبكات التأريض وفق IEEE 80.", "IEEE 80"),
    ("تحديد مقاومة شبكة التأريض وارتفاع جهد الأرض GPR.", "IEEE 80"),
    ("حدود التشويه التوافقي الكلي THD للجهد والتيار وفق IEEE 519.", "IEEE 519"),
]


class TestStructuredAnswerSchema:
    """Validate 100% Pydantic compliance for EngineerAnswer."""

    def test_valid_engineer_answer(self):
        answer_data = {
            "title": "Short Circuit Verification",
            "summary": "3-Phase fault study passed with zero overduty limits.",
            "status": "complete",
            "study_type": "SHORT_CIRCUIT",
            "findings": [
                {
                    "category": "Short Circuit",
                    "severity": "pass",
                    "message": "Ik'' = 25 kA is compliant with bus rating.",
                    "standard_reference": "IEC 60909-0",
                }
            ],
            "parameters": {"ik_initial_ka": 25.0, "ip_peak_ka": 62.5},
            "standards_referenced": ["IEC 60909", "IEC 62271-100"],
            "recommendations": ["Inspect breaker contact resistance prior to commissioning."],
            "confidence": 0.99,
        }
        ans = EngineerAnswer.model_validate(answer_data)
        assert ans.title == "Short Circuit Verification"
        assert ans.status == "complete"
        assert len(ans.findings) == 1
        assert ans.findings[0].severity == "pass"

    def test_schema_extra_fields_safely_ignored(self):
        answer_data = {
            "title": "Test Extra",
            "summary": "Testing resilience to unexpected LLM attributes.",
            "extra_llm_hallucination": "ignored safely",
        }
        ans = EngineerAnswer.model_validate(answer_data)
        assert ans.title == "Test Extra"
        assert not hasattr(ans, "extra_llm_hallucination")

    @pytest.mark.asyncio
    async def test_rag_query_fail_closed_503_when_no_provider(self):
        """Verify that rag_query returns HTTP 503 when no embedding provider is configured."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from api.ai_ml import rag_query

        req = MagicMock()
        req.state.trace_id = "test-503-trace"
        req.json = AsyncMock(return_value={"query": "test query", "top_k": 3})

        with patch("knowledge.rag_engine.EngineeringKnowledgeBase") as mock_kb:
            mock_kb.side_effect = RuntimeError("No embedding provider available.")
            response = await rag_query(req)
            assert response.status_code == 503


class TestRAGRetrievalBilingual:
    """Validate Top-3 retrieval on 30 Arabic and English engineering queries."""

    @pytest.fixture(scope="class")
    def populated_kb(self):
        kb = EngineeringKnowledgeBase()
        # Seed test documents for the standards
        standards_docs = [
            (
                "doc_iec60909",
                "IEC 60909-0:2016 Short-circuit currents in three-phase a.c. systems. "
                "Calculation of initial symmetrical short-circuit current Ik'', peak current ip using factor kappa, "
                "symmetrical breaking current Ib for near and far generator faults, and steady-state current Ik. "
                "معيار IEC 60909 لحساب تيارات القصر ثلاثية الأوجه، وتيار القمة ip، وتيار القطع Ib ومكافئ الإجهاد الحراري Ith.",
                "IEC 60909",
            ),
            (
                "doc_ieee1584",
                "IEEE 1584-2018 Guide for Performing Arc-Flash Hazard Calculations. "
                "Equations for incident energy cal/cm2 and arc flash boundary mm across electrode configurations VCB, VCBB, HCB. "
                "معيار IEEE 1584 لحساب طاقة الوميض القوسي وحدود الأمان وترتيب الأقطاب VCB و VCBB في لوحات الجهد المنخفض والمتوسط.",
                "IEEE 1584",
            ),
            (
                "doc_iec60255",
                "IEC 60255 Measuring relays and protection equipment. "
                "Time-current curve characteristics, standard inverse, very inverse, extremely inverse, grading margins. "
                "المواصفة القياسية IEC 60255 لتنسيق المرحلات وقواطع الحماية ومنحنيات الزمن والتيار TCC وهامش التنسيق الزمني.",
                "IEC 60255",
            ),
            (
                "doc_ieee3002",
                "IEEE 3002.7 Recommended Practice for Conducting Load-Flow Studies in Industrial and Commercial Power Systems. "
                "Newton-Raphson power flow equations, voltage limits, line thermal overloading, reactive power dispatch. "
                "معيار IEEE 3002.7 لدراسات سريان الأحمال وتوزيع القدرة وهبوط الجهد والتحكم في القدرة غير الفعالة.",
                "IEEE 3002.7",
            ),
            (
                "doc_ieee80",
                "IEEE 80 Guide for Safety in AC Substation Grounding. "
                "Mesh voltage, step voltage, touch voltage thresholds, ground grid resistance, and ground potential rise GPR. "
                "معيار IEEE 80 لتصميم شبكات التأريض وحساب جهد الخطوة وجهد اللمس ومقاومة شبكة الأرضي.",
                "IEEE 80",
            ),
            (
                "doc_ieee519",
                "IEEE 519-2022 Standard for Harmonic Control in Electric Power Systems. "
                "Voltage and current harmonic limits, Total Harmonic Distortion THD, Point of Common Coupling PCC. "
                "معيار IEEE 519 لحدود التوافقيات ونسبة التشويه التوافقي الكلي THD للجهد والتيار.",
                "IEEE 519",
            ),
            (
                "doc_nfpa70e",
                "NFPA 70E Standard for Electrical Safety in the Workplace. "
                "Personal protective equipment PPE category selection, arc-rated clothing, working distance. "
                "معيار NFPA 70E لمهمات الوقاية الشخصية PPE والسلامة المهنية من مخاطر القوس الكهربائي.",
                "NFPA 70E",
            ),
        ]

        for doc_id, text, std in standards_docs:
            chunks = chunk_document(text, doc_id=doc_id, standard=std)
            for c in chunks:
                doc = EngineeringDocument(
                    doc_id=c.chunk_id,
                    title=f"{std} Standard Guide",
                    source=std.split()[0] if std else "IEEE",
                    standard_number=std,
                    content=c.content,
                    metadata={"standard": std},
                )
                kb.ingest_document(doc)

        return kb

    def test_all_30_queries_top3_retrieval(self, populated_kb):
        success_count = 0
        total_queries = len(BENCHMARK_QUERIES)

        for query, expected_standard in BENCHMARK_QUERIES:
            results = populated_kb.retrieve_knowledge(query, top_k=3)
            # Check if expected standard is in top 3 results
            top_standards = [
                r.document.standard_number or r.document.source for r in results
            ]
            top_contents = " ".join(r.document.content for r in results)
            if any(expected_standard in s for s in top_standards) or expected_standard in top_contents:
                success_count += 1

        accuracy = success_count / total_queries
        print(f"Bilingual Top-3 RAG Accuracy: {success_count}/{total_queries} ({accuracy * 100:.1f}%)")
        assert accuracy >= 0.90, f"Expected >= 90% top-3 retrieval success, got {accuracy * 100:.1f}%"


class TestModel2VecIntegration:
    """Validate model2vec CPU embedding integration under rag_model2vec flag."""

    def test_default_behavior_preserves_sentence_transformers_when_flag_disabled(self, monkeypatch):
        from knowledge.rag_engine import EmbeddingModel

        monkeypatch.delenv("FEATURE_FLAG_RAG_MODEL2VEC", raising=False)
        em = EmbeddingModel(use_local=True)
        assert getattr(em, "_is_model2vec", False) is False

    def test_model2vec_active_when_flag_enabled(self, monkeypatch):
        from unittest.mock import MagicMock, patch

        import numpy as np

        from knowledge.rag_engine import EmbeddingModel

        monkeypatch.setenv("FEATURE_FLAG_RAG_MODEL2VEC", "true")

        mock_static_model = MagicMock()
        mock_static_model.encode.return_value = np.array([[0.1, 0.2, 0.3, 0.4]], dtype=np.float32)

        with patch("model2vec.StaticModel.from_pretrained", return_value=mock_static_model) as mock_pretrained:
            em = EmbeddingModel(use_local=True)
            assert getattr(em, "_is_model2vec", False) is True
            mock_pretrained.assert_called_once()

            embeddings = em.encode(["Sample electrical standard document"])
            assert isinstance(embeddings, np.ndarray)
            assert embeddings.shape == (1, 4)
            mock_static_model.encode.assert_called_once_with(["Sample electrical standard document"])

    def test_model2vec_fails_closed_on_load_error(self, monkeypatch):
        from unittest.mock import patch

        from knowledge.rag_engine import EmbeddingModel

        monkeypatch.setenv("FEATURE_FLAG_RAG_MODEL2VEC", "true")

        with patch("model2vec.StaticModel.from_pretrained", side_effect=Exception("Model weights corrupted")):
            with pytest.raises(RuntimeError, match="Failed to load model2vec model"):
                EmbeddingModel(use_local=True)
