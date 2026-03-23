"""Tests for WebPilot Agent — Growth Agent.

Tests the GrowthAgent: lead pipeline management, content arsenal,
outreach template selection, and workflow execution.
"""

import asyncio

import pytest
from pathlib import Path

from src.agents.base import AgentCapability, AgentStatus, AgentTask, BaseAgent
from src.agents.growth import GrowthAgent, LEAD_SCORES, CHANNELS


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def agent() -> GrowthAgent:
    return GrowthAgent(workflows_dir=Path("workflows/growth"))


# =========================================================================
# BaseAgent Protocol
# =========================================================================

class TestGrowthAgentProtocol:

    def test_implements_protocol(self, agent: GrowthAgent) -> None:
        assert isinstance(agent, BaseAgent)

    def test_name(self, agent: GrowthAgent) -> None:
        assert agent.name == "growth"

    def test_description(self, agent: GrowthAgent) -> None:
        assert "revenue" in agent.description.lower() or "growth" in agent.description.lower()

    def test_capabilities(self, agent: GrowthAgent) -> None:
        assert AgentCapability.BROWSER_AUTOMATION in agent.capabilities
        assert AgentCapability.DATA_EXTRACTION in agent.capabilities

    def test_status_idle(self, agent: GrowthAgent) -> None:
        assert agent.status == AgentStatus.IDLE

    def test_get_stats_initial(self, agent: GrowthAgent) -> None:
        stats = agent.get_stats()
        assert stats["total_tasks"] == 0
        assert stats["leads_found"] == 0
        assert stats["deals_closed"] == 0

    def test_unknown_action_fails(self, agent: GrowthAgent) -> None:
        result = run(agent.execute(AgentTask(action="nonexistent", task_id="t1")))
        assert not result.success
        assert "Unknown action" in (result.error or "")


# =========================================================================
# Workflow Loading
# =========================================================================

class TestGrowthWorkflows:

    def test_can_handle_all_workflows(self, agent: GrowthAgent) -> None:
        expected = [
            "find-hot-leads", "qualify-leads", "twitter-outreach",
            "linkedin-outreach", "email-outreach", "post-content", "track-pipeline",
        ]
        for name in expected:
            assert agent.can_handle(name), f"Agent should handle '{name}'"

    def test_cannot_handle_unknown(self, agent: GrowthAgent) -> None:
        assert not agent.can_handle("unknown-workflow")

    def test_get_actions(self, agent: GrowthAgent) -> None:
        actions = agent.get_actions()
        assert len(actions) == 7
        names = [a["name"] for a in actions]
        assert "find-hot-leads" in names
        assert "linkedin-outreach" in names
        assert "track-pipeline" in names


# =========================================================================
# Lead Pipeline Management
# =========================================================================

class TestLeadPipeline:

    def test_add_lead(self, agent: GrowthAgent) -> None:
        agent.add_lead("lead-1", {"name": "John", "type": "startup_cto", "company": "Acme"})
        assert agent.get_stats()["leads_found"] == 1

    def test_lead_scoring(self, agent: GrowthAgent) -> None:
        agent.add_lead("lead-1", {"name": "Agency Guy", "type": "dev_agency"})
        agent.add_lead("lead-2", {"name": "Indie Dev", "type": "indie_hacker"})
        hot = agent.get_hot_leads(min_score=70)
        assert len(hot) == 1  # Only agency (score 90) is hot
        assert hot[0]["id"] == "lead-1"

    def test_qualify_lead(self, agent: GrowthAgent) -> None:
        agent.add_lead("lead-1", {"name": "Test", "type": "startup_cto"})
        agent.qualify_lead("lead-1", qualified=True, notes="Good fit")
        assert agent.get_stats()["leads_qualified"] == 1
        leads = agent.get_leads_by_stage("qualified")
        assert len(leads) == 1

    def test_advance_lead_through_stages(self, agent: GrowthAgent) -> None:
        agent.add_lead("lead-1", {"name": "Test", "type": "startup_cto"})
        agent.advance_lead("lead-1", "contacted")
        assert agent.get_stats()["outreach_sent"] == 1
        agent.advance_lead("lead-1", "demo_scheduled")
        assert agent.get_stats()["demos_scheduled"] == 1
        agent.advance_lead("lead-1", "closed_won")
        assert agent.get_stats()["deals_closed"] == 1

    def test_pipeline_summary(self, agent: GrowthAgent) -> None:
        agent.add_lead("lead-1", {"name": "A", "type": "startup_cto"})
        agent.add_lead("lead-2", {"name": "B", "type": "dev_agency"})
        agent.advance_lead("lead-1", "contacted")
        summary = agent.get_pipeline_summary()
        assert summary["total_leads"] == 2
        assert summary["stages"]["discovered"] == 1
        assert summary["stages"]["contacted"] == 1

    def test_get_leads_by_stage(self, agent: GrowthAgent) -> None:
        agent.add_lead("lead-1", {"name": "A", "type": "startup_cto"})
        agent.add_lead("lead-2", {"name": "B", "type": "dev_agency"})
        agent.advance_lead("lead-1", "contacted")
        contacted = agent.get_leads_by_stage("contacted")
        assert len(contacted) == 1
        discovered = agent.get_leads_by_stage("discovered")
        assert len(discovered) == 1


# =========================================================================
# Content Arsenal
# =========================================================================

class TestContentArsenal:

    def test_get_content_for_twitter(self, agent: GrowthAgent) -> None:
        content = agent.get_content_for_channel("twitter")
        assert "threads" in content
        assert "dms" in content

    def test_get_content_for_linkedin(self, agent: GrowthAgent) -> None:
        content = agent.get_content_for_channel("linkedin")
        assert "posts" in content
        assert "outreach" in content

    def test_get_content_for_email(self, agent: GrowthAgent) -> None:
        content = agent.get_content_for_channel("email")
        assert "sequences" in content

    def test_get_content_for_unknown_channel(self, agent: GrowthAgent) -> None:
        content = agent.get_content_for_channel("tiktok")
        assert content == {}

    def test_outreach_template_for_agency_linkedin(self, agent: GrowthAgent) -> None:
        template = agent.get_outreach_template("dev_agency", "linkedin")
        assert "Agency" in template.get("template", "")

    def test_outreach_template_for_cto_linkedin(self, agent: GrowthAgent) -> None:
        template = agent.get_outreach_template("startup_cto", "linkedin")
        assert "CTO" in template.get("template", "")

    def test_outreach_template_fallback(self, agent: GrowthAgent) -> None:
        template = agent.get_outreach_template("unknown_type", "unknown_channel")
        assert "template" in template  # Returns generic fallback

    def test_best_channel_for_agency(self, agent: GrowthAgent) -> None:
        assert agent.get_best_channel("dev_agency") == "linkedin"

    def test_best_channel_for_indie_hacker(self, agent: GrowthAgent) -> None:
        assert agent.get_best_channel("indie_hacker") == "twitter"

    def test_best_channel_fallback(self, agent: GrowthAgent) -> None:
        assert agent.get_best_channel("unknown_type") == "linkedin"


# =========================================================================
# Lessons & Reports
# =========================================================================

class TestLessonsAndReports:

    def test_lessons_when_leads_but_no_outreach(self, agent: GrowthAgent) -> None:
        agent._stats["leads_found"] = 15
        lessons = agent.get_lessons()
        assert any("outreach" in l["message"].lower() for l in lessons)

    def test_lessons_when_outreach_but_no_demos(self, agent: GrowthAgent) -> None:
        agent._stats["outreach_sent"] = 20
        lessons = agent.get_lessons()
        assert any("demo" in l["message"].lower() or "messaging" in l["message"].lower() for l in lessons)

    def test_lessons_when_deals_closed(self, agent: GrowthAgent) -> None:
        agent._stats["deals_closed"] = 3
        lessons = agent.get_lessons()
        assert any("winning" in l["message"].lower() or "closed" in l["message"].lower() for l in lessons)

    def test_weekly_report(self, agent: GrowthAgent) -> None:
        agent.add_lead("lead-1", {"name": "Test", "type": "startup_cto"})
        agent.advance_lead("lead-1", "contacted")
        report = agent.generate_weekly_report()
        assert "stats" in report
        assert "pipeline" in report
        assert "next_actions" in report
        assert len(report["next_actions"]) > 0

    def test_next_actions_when_empty_pipeline(self, agent: GrowthAgent) -> None:
        report = agent.generate_weekly_report()
        assert any("find" in a.lower() for a in report["next_actions"])


# =========================================================================
# Lead Scores & Channels Constants
# =========================================================================

class TestConstants:

    def test_lead_scores_exist(self) -> None:
        assert LEAD_SCORES["dev_agency"] == 90
        assert LEAD_SCORES["startup_cto"] == 85
        assert LEAD_SCORES["indie_hacker"] == 60

    def test_channels_have_priorities(self) -> None:
        assert CHANNELS["twitter"]["priority"] < CHANNELS["email"]["priority"]
        assert CHANNELS["linkedin"]["priority"] < CHANNELS["reddit"]["priority"]

    def test_channels_have_best_for(self) -> None:
        assert "indie_hacker" in CHANNELS["twitter"]["best_for"]
        assert "startup_cto" in CHANNELS["linkedin"]["best_for"]
