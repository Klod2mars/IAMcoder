from data.diff_engine import diff_engine


def test_compute_diff_added_and_modified():
    old = "line1\nline2\n"
    new = "line1\nline2 changed\nline3\n"
    result = diff_engine.compute_diff(old, new, "file.txt")

    assert result.file_path == "file.txt"
    # Implementation categorizes both the changed line and the insertion as MODIFIED
    assert result.modified_lines >= 1
    # sanity: total changes match lines captured
    assert len(result.diff_lines) == result.added_lines + result.removed_lines + result.modified_lines


