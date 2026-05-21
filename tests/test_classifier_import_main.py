def test_main_imports_without_error():
    try:
        import main
        success = True
    except NameError:
        success = False
    assert success
