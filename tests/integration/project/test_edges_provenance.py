

def test_edge_payload_dedup_and_coexistence(tmp_path, schema_uow_factory):
    uow = schema_uow_factory()
    with uow as uu:
        src = "s:1"
        dst = "d:1"
        kind = "included_in_dataset"

        uu.edges.add(src_uid_full=src, dst_uid_full=dst, kind=kind, payload={"dataset_index": 0})
        uu.edges.add(src_uid_full=src, dst_uid_full=dst, kind=kind, payload={"dataset_index": 1})

        rows = uu.edges.list(src_uid_full=src)
        assert len(rows) == 2
        phs = {r.payload.get("dataset_index") for r in rows}
        assert phs == {0, 1}

        # duplicate payload should dedupe
        uu.edges.add(src_uid_full=src, dst_uid_full=dst, kind=kind, payload={"dataset_index": 1})
        rows2 = uu.edges.list(src_uid_full=src)
        assert len(rows2) == 2

        # dataset_item_uses_artifact edges should also be insertable and deduped
        art_uid = "artifact:deadbeef"
        uu.edges.add(src_uid_full=src, dst_uid_full=art_uid, kind="dataset_item_uses_artifact", payload={"artifact_uid_full": art_uid})
        # duplicate insert ignored
        uu.edges.add(src_uid_full=src, dst_uid_full=art_uid, kind="dataset_item_uses_artifact", payload={"artifact_uid_full": art_uid})
        rows3 = uu.edges.list(src_uid_full=src, kind="dataset_item_uses_artifact")
        assert len(rows3) == 1
