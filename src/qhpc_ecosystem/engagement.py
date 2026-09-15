"""Read-only Engagement Thrust resources shared across EQO surfaces.

These records are intentionally separate from the capability registry.  They
describe public learning and community destinations; none admits a tool,
service, runtime, credential, or workflow target into EQO.
"""

from __future__ import annotations

from typing import Any


_RESOURCES: tuple[dict[str, str], ...] = (
    {
        "id": "hpc-ai-qc-crash-course",
        "title": "HPC / AI / QC Crash Course",
        "kind": "course-materials",
        "provider": "OLCF",
        "url": "https://github.com/olcf/hands-on-with-odo",
        "description": (
            "Hands-on course material with a session agenda, presentations, "
            "and challenges."
        ),
        "admission": "read-only-external-resource",
    },
    {
        "id": "quantum-computing-user-training",
        "title": "Quantum Computing User Training",
        "kind": "tutorial-materials",
        "provider": "OLCF",
        "url": "https://github.com/olcf/quantum-training-series",
        "description": (
            "Quantum Training Series tutorials covering workflows, tools, "
            "software, and techniques in HPC and beyond."
        ),
        "admission": "read-only-external-resource",
    },
    {
        "id": "fall-2026-qcup-hackathon",
        "title": "Quantum Computing Hackathon",
        "kind": "community-event",
        "provider": "OLCF",
        "url": "https://www.olcf.ornl.gov/calendar/fall-2026-qcup-hackathon/",
        "description": (
            "The Fall 2026 QCUP Hackathon is a virtual, multi-day event for "
            "teams advancing fundamental scientific research through quantum computing."
        ),
        "admission": "read-only-external-resource",
    },
)


def engagement_catalog() -> dict[str, Any]:
    """Return a fresh, side-effect-free public Engagement catalog."""

    return {
        "kind": "EngagementResources",
        "read_only": True,
        "resources": [dict(resource) for resource in _RESOURCES],
    }
