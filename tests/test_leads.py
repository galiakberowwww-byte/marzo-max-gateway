from app.leads import LeadDraft, LeadStore


def test_qualified_lead_is_persisted(tmp_path) -> None:
    store = LeadStore(str(tmp_path / "marzo.sqlite3"))
    lead_id = store.save(
        LeadDraft(
            max_user_id="42",
            source="qr_showroom",
            direction="Дизайн",
            answers={"object": "квартира", "location": "Уфа"},
        ),
        phone=None,
        customer_name="Клиент",
    )
    assert lead_id.startswith("MRZ-")
