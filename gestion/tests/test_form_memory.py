"""Validation tests for GestionMemoryForm — the form behind /gestion/souvenirs/.

Lifts memoires.forms.MemoryAdminForm into the gestion namespace and adds
the upload size/MIME guards the existing admin form doesn't enforce.
"""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def _make_jpeg_upload(
    *, size_bytes: int = 1024, content_type: str = "image/jpeg", name: str = "test.jpg"
) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"x" * size_bytes, content_type=content_type)


class TestGestionMemoryFormCreate:
    def test_valid_form_with_upload_passes(self):
        from gestion.forms import GestionMemoryForm

        form = GestionMemoryForm(
            data={
                "caption": "Sortie à Birni 1983",
                "taken_at": "",
                "location": "Birni",
                "status": "draft",
            },
            files={"upload": _make_jpeg_upload()},
        )
        assert form.is_valid(), form.errors

    def test_missing_upload_on_create_fails(self):
        from gestion.forms import GestionMemoryForm

        form = GestionMemoryForm(
            data={
                "caption": "Sortie à Birni 1983",
                "taken_at": "",
                "location": "Birni",
                "status": "draft",
            },
            files={},
        )
        assert not form.is_valid()
        errors_text = str(form.errors)
        assert "photo" in errors_text.lower() or "obligatoire" in errors_text.lower()

    def test_oversize_upload_rejected(self):
        from gestion.forms import GestionMemoryForm

        big = _make_jpeg_upload(size_bytes=9 * 1024 * 1024)
        form = GestionMemoryForm(
            data={"caption": "x", "location": "", "status": "draft", "taken_at": ""},
            files={"upload": big},
        )
        assert not form.is_valid()
        assert "upload" in form.errors
        assert "8" in str(form.errors["upload"])

    def test_zero_byte_upload_rejected(self):
        from gestion.forms import GestionMemoryForm

        empty = _make_jpeg_upload(size_bytes=0)
        form = GestionMemoryForm(
            data={"caption": "x", "location": "", "status": "draft", "taken_at": ""},
            files={"upload": empty},
        )
        assert not form.is_valid()
        assert "upload" in form.errors

    def test_disallowed_mime_rejected(self):
        from gestion.forms import GestionMemoryForm

        bad = SimpleUploadedFile("file.gif", b"x" * 100, content_type="image/gif")
        form = GestionMemoryForm(
            data={"caption": "x", "location": "", "status": "draft", "taken_at": ""},
            files={"upload": bad},
        )
        assert not form.is_valid()
        assert "upload" in form.errors

    def test_jpeg_png_webp_all_accepted(self):
        from gestion.forms import GestionMemoryForm

        for ctype, name in [
            ("image/jpeg", "p.jpg"),
            ("image/png", "p.png"),
            ("image/webp", "p.webp"),
        ]:
            up = _make_jpeg_upload(content_type=ctype, name=name)
            form = GestionMemoryForm(
                data={"caption": "x", "location": "", "status": "draft", "taken_at": ""},
                files={"upload": up},
            )
            assert form.is_valid(), f"{ctype} should validate; got {form.errors}"


class TestGestionMemoryFormEdit:
    def test_edit_without_new_upload_passes(self, make_memory):
        from gestion.forms import GestionMemoryForm

        memory = make_memory()
        form = GestionMemoryForm(
            data={
                "caption": "Updated caption",
                "taken_at": "",
                "location": "",
                "status": "published",
            },
            files={},
            instance=memory,
        )
        assert form.is_valid(), form.errors

    def test_edit_with_new_upload_passes(self, make_memory):
        from gestion.forms import GestionMemoryForm

        memory = make_memory()
        form = GestionMemoryForm(
            data={
                "caption": "Updated",
                "taken_at": "",
                "location": "",
                "status": "draft",
            },
            files={"upload": _make_jpeg_upload()},
            instance=memory,
        )
        assert form.is_valid(), form.errors
