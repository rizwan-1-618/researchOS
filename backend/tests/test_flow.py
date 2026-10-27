from io import BytesIO

from fpdf import FPDF


def _pdf(text: str) -> bytes:
    document = FPDF()
    document.add_page()
    document.set_font("Helvetica", size=16)
    document.cell(text=text)
    return bytes(document.output())


def test_research_flow(client):
    register = client.post(
        "/api/auth/register",
        json={"name": "Ada Lovelace", "email": "ada@example.com", "password": "correct-horse"},
    )
    assert register.status_code == 201, register.text
    assert client.get("/api/auth/me").status_code == 200

    profile = client.put(
        "/api/users/me/profile",
        json={
            "research_interests": ["Quantum machine learning"],
            "skills": ["Python"],
            "preferred_topics": ["Kernels"],
        },
    )
    assert profile.status_code == 200
    assert profile.json()["profile"]["research_interests"] == ["Quantum machine learning"]

    project = client.post("/api/projects", json={"name": "QML Research", "description": "Classification kernels"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    concept = client.post("/api/concepts", json={"name": "Quantum kernels", "description": "Feature maps"})
    assert concept.status_code == 201, concept.text
    concept_id = concept.json()["id"]

    question = client.post(
        "/api/questions",
        json={"title": "Can quantum kernels help?", "project_id": project_id, "status": "draft"},
    )
    assert question.status_code == 201, question.text
    question_id = question.json()["id"]
    moved = client.patch(f"/api/questions/{question_id}", json={"status": "investigating"})
    assert moved.status_code == 200
    blocked = client.patch(f"/api/questions/{question_id}", json={"status": "completed"})
    assert blocked.status_code == 409

    paper = client.post(
        "/api/papers",
        json={
            "title": "Quantum Kernel Methods",
            "abstract": "Quantum kernels map classical data into high-dimensional Hilbert spaces.",
            "year": 2024,
            "authors": [{"name": "Grace Hopper", "affiliation": "Navy"}],
        },
    )
    assert paper.status_code == 201, paper.text
    paper_id = paper.json()["id"]
    assert paper.json()["authors"][0]["name"] == "Grace Hopper"

    assert client.post(f"/api/projects/{project_id}/papers", json={"ids": [paper_id]}).status_code == 204
    tagged = client.post(f"/api/papers/{paper_id}/tags", json={"name": "kernels"})
    assert tagged.status_code == 201
    assert (
        client.post(
            f"/api/papers/{paper_id}/concepts",
            json={"concept_id": concept_id, "relationship_type": "about"},
        ).status_code
        == 204
    )
    assert client.post(f"/api/questions/{question_id}/papers", json={"ids": [paper_id]}).status_code == 204

    note = client.post(
        "/api/notes",
        json={
            "content": "Important connection to feature maps.",
            "paper_id": paper_id,
            "project_id": project_id,
            "concept_ids": [concept_id],
            "question_ids": [question_id],
        },
    )
    assert note.status_code == 201, note.text

    highlight = client.post(
        "/api/highlights",
        json={
            "paper_id": paper_id,
            "page": 1,
            "selected_text": "Quantum kernels map classical data",
            "comment": "Feature maps",
            "rects": [{"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.05}],
            "concept_ids": [concept_id],
            "question_ids": [question_id],
        },
    )
    assert highlight.status_code == 201, highlight.text

    task = client.post(
        "/api/tasks",
        json={
            "title": "Read the kernel paper",
            "project_id": project_id,
            "paper_id": paper_id,
            "question_id": question_id,
            "priority": "high",
        },
    )
    assert task.status_code == 201, task.text
    done = client.patch(f"/api/tasks/{task.json()['id']}", json={"status": "done"})
    assert done.status_code == 200
    assert done.json()["completed_at"]

    library = client.get("/api/papers?q=Hilbert")
    assert library.status_code == 200, library.text
    assert library.json()["total"] == 1

    search = client.get("/api/search", params={"q": "Hilbert spaces", "mode": "keyword"})
    assert search.status_code == 200, search.text
    assert search.json()["papers"]

    semantic = client.get("/api/search", params={"q": "feature maps", "mode": "semantic"})
    assert semantic.status_code == 200, semantic.text

    graph = client.get("/api/graph", params={"scope": "project", "focus": project_id})
    assert graph.status_code == 200, graph.text
    assert any(node["type"] == "paper" for node in graph.json()["nodes"])

    opened = client.post(f"/api/papers/{paper_id}/opened")
    assert opened.status_code == 204
    completed = client.patch(f"/api/papers/{paper_id}/library", json={"status": "completed", "is_important": True})
    assert completed.status_code == 200
    analytics = client.get("/api/analytics/overview")
    assert analytics.status_code == 200, analytics.text
    body = analytics.json()
    assert body["papers_completed"] == 1
    assert body["notes"] == 1
    assert body["projects"] == 1

    upload = client.post(
        "/api/papers/upload",
        files={"file": ("notes.pdf", BytesIO(_pdf("Quantum kernels map data.")), "application/pdf")},
        data={"title": "Uploaded note"},
    )
    assert upload.status_code == 201, upload.text
    uploaded_id = upload.json()["id"]
    downloaded = client.get(f"/api/papers/{uploaded_id}/file")
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    login = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "correct-horse"})
    assert login.status_code == 200
