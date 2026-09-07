from app.services.expressions import render_template


def test_render_legacy_input_alias():
    ctx = {"input": {"text": "hello"}, "steps": {}, "last_output": "hello"}
    assert render_template("{{input}}", ctx, "hello") == "hello"


def test_render_input_text():
    ctx = {"input": {"text": "hello", "name": "Ada"}, "steps": {}, "last_output": "hello"}
    assert render_template("Hi {{input.name}}", ctx, "hello") == "Hi Ada"


def test_render_step_output():
    ctx = {
        "input": {"text": "start"},
        "steps": {"agent_1": {"output": "summary text", "label": "Agent"}},
        "last_output": "summary text",
    }
    assert (
        render_template("Based on: {{steps.agent_1.output}}", ctx, "ignored")
        == "Based on: summary text"
    )


def test_render_last_output():
    ctx = {"input": {"text": "x"}, "steps": {}, "last_output": "latest"}
    assert render_template("Echo: {{last_output}}", ctx, "upstream") == "Echo: latest"


def test_render_memory_path():
    ctx = {
        "input": {"text": "x"},
        "steps": {},
        "last_output": "latest",
        "memory": {"prefs": {"theme": "dark"}},
    }
    assert render_template("Theme={{memory.prefs.theme}}", ctx, "x") == "Theme=dark"


def test_render_plain_template_without_expressions():
    assert render_template("static", {}, "in") == "static"


def test_evaluate_condition_eq():
    from app.services.expressions import evaluate_condition

    ctx = {"input": {"priority": "high"}, "steps": {}, "last_output": "x"}
    assert evaluate_condition("{{input.priority}}", "eq", "high", ctx, "x")
    assert not evaluate_condition("{{input.priority}}", "eq", "low", ctx, "x")


def test_evaluate_condition_not_empty():
    from app.services.expressions import evaluate_condition

    ctx = {"input": {}, "steps": {}, "last_output": "hello"}
    assert evaluate_condition("{{last_output}}", "not_empty", None, ctx, "hello")
    assert not evaluate_condition("{{last_output}}", "empty", None, ctx, "")