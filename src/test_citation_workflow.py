from citation_workflow import Citation, dedupe_citations, notification_decision


def test_research_note_keeps_one_source_and_routes_patient_notice_to_review():
    citations = [
        Citation("Clinic workflow", "https://example.org/guide/", "A"),
        Citation("Clinic workflow copy", "https://example.org/guide#section", "B"),
    ]

    unique = dedupe_citations(citations)

    assert len(unique) == 1
    assert notification_decision("Patient appointment reminder") == "human_review"
    assert notification_decision("General literature digest") == "send"
