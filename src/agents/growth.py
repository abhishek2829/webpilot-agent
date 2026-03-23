"""WebPilot Agent — Growth Agent.

The revenue engine. This agent's sole purpose is to grow the WebPilot
business by finding leads, qualifying them, running outreach campaigns,
nurturing prospects, and converting them into paying customers.

It uses the marketing content in marketing/ as ammunition and chains
with the Research, Sales, and Marketing agents to execute full
growth pipelines.

Responsibilities:
  1. FIND — Discover potential customers on Twitter, LinkedIn, Reddit,
     Product Hunt, Indie Hackers, Hacker News
  2. QUALIFY — Research each lead to determine fit (dev agency? startup CTO?
     indie hacker? DevOps engineer?)
  3. REACH — Execute personalized outreach using the pre-built templates
     (DMs, emails, LinkedIn connections, social posts)
  4. NURTURE — Follow up, share content, engage with their posts
  5. CONVERT — Track pipeline, schedule demos, close deals
  6. GROW — Post content, launch on platforms, build community

Growth Pipelines:
  - lead-gen-pipeline: Find leads on social platforms -> qualify -> add to CRM
  - nurture-convert-pipeline: Outreach -> follow-up -> demo -> close
  - content-distribute-pipeline: Post blog -> tweet thread -> LinkedIn -> Reddit
  - weekly-growth-cycle: All of the above in a weekly cadence
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.agents.base import (
    AgentCapability,
    AgentResult,
    AgentStatus,
    AgentTask,
)
from src.core.workflow_registry import WorkflowNotFoundError, WorkflowRegistry

logger = logging.getLogger(__name__)


# Where the marketing content lives — the agent's ammunition
MARKETING_CONTENT_DIR = Path("./marketing")

# Lead scoring criteria
LEAD_SCORES = {
    "dev_agency": 90,       # Highest value — recurring client projects
    "startup_cto": 85,      # High value — team plans
    "devops_lead": 80,      # High value — team adoption
    "indie_hacker": 60,     # Medium — individual Pro plans
    "sales_leader": 70,     # Medium-high — sales agent adoption
    "developer": 50,        # Lower — free tier, potential upgrade
}

# Outreach channels and their priority
CHANNELS = {
    "twitter": {"priority": 1, "best_for": ["indie_hacker", "developer"]},
    "linkedin": {"priority": 2, "best_for": ["startup_cto", "devops_lead", "dev_agency", "sales_leader"]},
    "email": {"priority": 3, "best_for": ["dev_agency", "startup_cto"]},
    "reddit": {"priority": 4, "best_for": ["developer", "indie_hacker"]},
    "producthunt": {"priority": 5, "best_for": ["indie_hacker", "developer"]},
}


class GrowthAgent:
    """Growth agent — finds leads, runs outreach, converts customers, grows revenue.

    This agent is the business engine of WebPilot. It:
    1. Scans social platforms for potential customers (people complaining about
       repetitive setup, manual research, tedious outreach)
    2. Qualifies leads by researching their profile and company
    3. Executes personalized outreach using pre-built templates
    4. Tracks the sales pipeline and follows up
    5. Posts content to build awareness and inbound leads
    6. Reports on growth metrics weekly

    Usage:
        agent = GrowthAgent()

        # Find and qualify leads
        task = AgentTask(action="find-hot-leads", parameters={
            "platform": "twitter",
            "search_queries": "setting up Clerk,Supabase setup takes forever,DevOps automation"
        })
        result = await agent.execute(task)

        # Run outreach campaign
        task = AgentTask(action="linkedin-outreach-campaign", parameters={
            "lead_type": "startup_cto",
            "batch_size": "10"
        })
        result = await agent.execute(task)
    """

    def __init__(self, workflows_dir: Path = Path("./workflows/growth")) -> None:
        self._workflows_dir = workflows_dir
        self._registry = WorkflowRegistry(workflows_dir=workflows_dir)
        self._registry.load_all()
        self._status = AgentStatus.IDLE
        self._marketing_dir = MARKETING_CONTENT_DIR

        # Sales pipeline tracking
        self._pipeline: dict[str, dict[str, Any]] = {}  # lead_id -> lead info
        self._stats = {
            "total_tasks": 0,
            "completed": 0,
            "failed": 0,
            "leads_found": 0,
            "leads_qualified": 0,
            "outreach_sent": 0,
            "demos_scheduled": 0,
            "deals_closed": 0,
            "revenue_generated": 0,
        }
        self._task_log: list[dict[str, Any]] = []
        self._weekly_reports: list[dict[str, Any]] = []

    # =========================================================================
    # BaseAgent Protocol
    # =========================================================================

    @property
    def name(self) -> str:
        return "growth"

    @property
    def description(self) -> str:
        return (
            "Revenue growth engine — finds hot leads on Twitter/LinkedIn/Reddit, "
            "qualifies prospects, runs personalized outreach campaigns using pre-built "
            "templates, nurtures leads, schedules demos, and tracks the sales pipeline. "
            "Uses marketing content from marketing/ as ammunition."
        )

    @property
    def capabilities(self) -> list[AgentCapability]:
        return sorted([
            AgentCapability.BROWSER_AUTOMATION,
            AgentCapability.DATA_EXTRACTION,
            AgentCapability.FORM_FILLING,
        ], key=lambda c: c.value)

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def execute(self, task: AgentTask) -> AgentResult:
        task_id = task.task_id or f"growth-{uuid4().hex[:12]}"
        start_time = time.monotonic()
        self._status = AgentStatus.BUSY
        self._stats["total_tasks"] += 1

        try:
            workflow = self._registry.get(task.action)

            from src.browser.actions import ActionEngine
            from src.browser.session import BrowserSession
            from src.checkpoints.manager import CheckpointManager
            from src.core.executor import WorkflowExecutor
            from src.core.recovery import RecoveryEngine

            checkpoint_mgr = CheckpointManager(mode=task.checkpoint_mode, timeout_seconds=300)
            llm_brain = None
            try:
                import os
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if api_key:
                    from src.core.llm_brain import LLMBrain
                    llm_brain = LLMBrain(api_key=api_key)
            except Exception:
                pass

            action_engine = ActionEngine(llm_brain=llm_brain)
            recovery_engine = RecoveryEngine(
                action_engine=action_engine,
                llm_brain=llm_brain,
                checkpoint_manager=checkpoint_mgr,
            )
            executor = WorkflowExecutor(
                action_engine=action_engine,
                checkpoint_manager=checkpoint_mgr,
                recovery_engine=recovery_engine,
            )

            session = BrowserSession(headless=task.headless)
            try:
                await session.start()
                result = await executor.execute(
                    workflow=workflow,
                    session=session,
                    variables=task.parameters,
                )
            finally:
                await session.close()

            duration_ms = int((time.monotonic() - start_time) * 1000)
            from src.core.models import ExecutionStatus

            if result.status == ExecutionStatus.COMPLETED:
                self._stats["completed"] += 1
                self._update_pipeline_stats(task.action, result.extracted_variables)
                self._status = AgentStatus.IDLE
                return AgentResult(
                    task_id=task_id,
                    agent_name=self.name,
                    success=True,
                    data={
                        "execution_id": result.id,
                        "extracted_variables": result.extracted_variables,
                        "steps_completed": len(result.step_results),
                        "pipeline_stats": self.get_pipeline_summary(),
                    },
                    duration_ms=duration_ms,
                )
            else:
                self._stats["failed"] += 1
                self._status = AgentStatus.IDLE
                return AgentResult(
                    task_id=task_id,
                    agent_name=self.name,
                    success=False,
                    data={"status": result.status.value},
                    error=result.error,
                    duration_ms=duration_ms,
                )

        except WorkflowNotFoundError as e:
            self._stats["failed"] += 1
            self._status = AgentStatus.IDLE
            return AgentResult(
                task_id=task_id,
                agent_name=self.name,
                success=False,
                error=f"Unknown action: {task.action}. {e}",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
        except Exception as e:
            self._stats["failed"] += 1
            self._status = AgentStatus.ERROR
            return AgentResult(
                task_id=task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
        finally:
            self._task_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task_id": task_id,
                "action": task.action,
            })

    def can_handle(self, action: str) -> bool:
        return self._registry.exists(action)

    def get_actions(self) -> list[dict[str, str]]:
        return [
            {"name": wf["name"], "description": wf["description"]}
            for wf in self._registry.list_workflows()
        ]

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)

    # =========================================================================
    # Pipeline Management
    # =========================================================================

    def add_lead(self, lead_id: str, lead_data: dict[str, Any]) -> None:
        """Add a lead to the sales pipeline."""
        lead_data["added_at"] = datetime.now(timezone.utc).isoformat()
        lead_data["stage"] = lead_data.get("stage", "discovered")
        lead_data["score"] = LEAD_SCORES.get(lead_data.get("type", "developer"), 50)
        self._pipeline[lead_id] = lead_data
        self._stats["leads_found"] += 1

    def qualify_lead(self, lead_id: str, qualified: bool, notes: str = "") -> None:
        """Mark a lead as qualified or disqualified."""
        if lead_id in self._pipeline:
            self._pipeline[lead_id]["stage"] = "qualified" if qualified else "disqualified"
            self._pipeline[lead_id]["qualification_notes"] = notes
            if qualified:
                self._stats["leads_qualified"] += 1

    def advance_lead(self, lead_id: str, new_stage: str) -> None:
        """Move a lead to the next pipeline stage."""
        valid_stages = ["discovered", "qualified", "contacted", "responded", "demo_scheduled", "proposal_sent", "closed_won", "closed_lost"]
        if lead_id in self._pipeline and new_stage in valid_stages:
            self._pipeline[lead_id]["stage"] = new_stage
            self._pipeline[lead_id][f"{new_stage}_at"] = datetime.now(timezone.utc).isoformat()
            if new_stage == "contacted":
                self._stats["outreach_sent"] += 1
            elif new_stage == "demo_scheduled":
                self._stats["demos_scheduled"] += 1
            elif new_stage == "closed_won":
                self._stats["deals_closed"] += 1

    def get_pipeline_summary(self) -> dict[str, Any]:
        """Get a summary of the current sales pipeline."""
        stages: dict[str, int] = {}
        for lead in self._pipeline.values():
            stage = lead.get("stage", "unknown")
            stages[stage] = stages.get(stage, 0) + 1

        hot_leads = [
            {"id": lid, **ldata}
            for lid, ldata in self._pipeline.items()
            if ldata.get("score", 0) >= 70 and ldata.get("stage") not in ("closed_won", "closed_lost", "disqualified")
        ]

        return {
            "total_leads": len(self._pipeline),
            "stages": stages,
            "hot_leads_count": len(hot_leads),
            "conversion_rate": (
                f"{(self._stats['deals_closed'] / self._stats['leads_found'] * 100):.1f}%"
                if self._stats["leads_found"] > 0 else "0%"
            ),
        }

    def get_hot_leads(self, min_score: int = 70) -> list[dict[str, Any]]:
        """Get leads with score >= min_score that haven't been closed."""
        return [
            {"id": lid, **ldata}
            for lid, ldata in self._pipeline.items()
            if ldata.get("score", 0) >= min_score
            and ldata.get("stage") not in ("closed_won", "closed_lost", "disqualified")
        ]

    def get_leads_by_stage(self, stage: str) -> list[dict[str, Any]]:
        """Get all leads at a specific pipeline stage."""
        return [
            {"id": lid, **ldata}
            for lid, ldata in self._pipeline.items()
            if ldata.get("stage") == stage
        ]

    # =========================================================================
    # Content Arsenal
    # =========================================================================

    def get_content_for_channel(self, channel: str) -> dict[str, str]:
        """Get the right marketing content file paths for a channel."""
        content_map = {
            "twitter": {
                "threads": "week1-social-proof/twitter-threads.md",
                "dms": "week1-social-proof/beta-outreach-dms.md",
            },
            "linkedin": {
                "posts": "week1-social-proof/linkedin-posts.md",
                "outreach": "week4-outbound/linkedin-outreach-templates.md",
                "dms": "week1-social-proof/beta-outreach-dms.md",
            },
            "email": {
                "sequences": "week4-outbound/cold-email-sequences.md",
                "partnerships": "week4-outbound/partnership-pitch.md",
            },
            "reddit": {
                "posts": "week3-launch/reddit-posts.md",
            },
            "producthunt": {
                "listing": "week3-launch/product-hunt-listing.md",
            },
            "hackernews": {
                "post": "week3-launch/hacker-news-post.md",
            },
            "indiehackers": {
                "post": "week3-launch/indie-hackers-post.md",
            },
            "blog": {
                "saas_setup": "week2-content/blog-saas-setup-automation.md",
                "sales_pipeline": "week2-content/blog-ai-sales-pipeline.md",
            },
        }
        return content_map.get(channel, {})

    def get_outreach_template(self, lead_type: str, channel: str) -> dict[str, str]:
        """Get the best outreach template for a lead type + channel combination."""
        templates = {
            ("dev_agency", "linkedin"): {
                "template": "Template 1: Agency Founders",
                "file": "week4-outbound/linkedin-outreach-templates.md",
                "email_sequence": "Sequence 1: Dev Agency Founders",
            },
            ("startup_cto", "linkedin"): {
                "template": "Template 3: Startup CTOs",
                "file": "week4-outbound/linkedin-outreach-templates.md",
                "email_sequence": "Sequence 2: Startup CTOs / DevOps Leads",
            },
            ("devops_lead", "linkedin"): {
                "template": "Template 2: DevOps Engineers",
                "file": "week4-outbound/linkedin-outreach-templates.md",
                "email_sequence": "Sequence 2: Startup CTOs / DevOps Leads",
            },
            ("sales_leader", "linkedin"): {
                "template": "Template 4: Sales Professionals",
                "file": "week4-outbound/linkedin-outreach-templates.md",
                "email_sequence": "Sequence 3: Sales Leaders",
            },
            ("indie_hacker", "twitter"): {
                "template": "DM 1: To an indie hacker",
                "file": "week1-social-proof/beta-outreach-dms.md",
            },
            ("developer", "twitter"): {
                "template": "DM 3: To a DevOps engineer",
                "file": "week1-social-proof/beta-outreach-dms.md",
            },
        }
        return templates.get((lead_type, channel), {
            "template": "Generic outreach",
            "file": "week1-social-proof/beta-outreach-dms.md",
        })

    def get_best_channel(self, lead_type: str) -> str:
        """Determine the best outreach channel for a lead type."""
        for channel, info in sorted(CHANNELS.items(), key=lambda x: x[1]["priority"]):
            if lead_type in info["best_for"]:
                return channel
        return "linkedin"  # Default fallback

    # =========================================================================
    # Internal
    # =========================================================================

    def _update_pipeline_stats(self, action: str, extracted: dict[str, str]) -> None:
        """Update pipeline stats based on completed workflow action."""
        if "find" in action or "lead" in action:
            self._stats["leads_found"] += len(extracted)
        if "outreach" in action or "connect" in action:
            self._stats["outreach_sent"] += 1

    def get_lessons(self) -> list[dict[str, Any]]:
        """Return insights from growth operations."""
        lessons = []
        if self._stats["leads_found"] > 0 and self._stats["outreach_sent"] == 0:
            lessons.append({
                "type": "action_gap",
                "message": f"Found {self._stats['leads_found']} leads but sent 0 outreach. Time to start reaching out.",
            })
        if self._stats["outreach_sent"] > 10 and self._stats["demos_scheduled"] == 0:
            lessons.append({
                "type": "conversion_issue",
                "message": f"Sent {self._stats['outreach_sent']} outreach messages but 0 demos scheduled. Review messaging.",
            })
        if self._stats["deals_closed"] > 0:
            lessons.append({
                "type": "winning_pattern",
                "message": f"Closed {self._stats['deals_closed']} deals. Analyze what worked and double down.",
            })
        return lessons

    def generate_weekly_report(self) -> dict[str, Any]:
        """Generate a weekly growth report."""
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": dict(self._stats),
            "pipeline": self.get_pipeline_summary(),
            "hot_leads": len(self.get_hot_leads()),
            "lessons": self.get_lessons(),
            "next_actions": self._suggest_next_actions(),
        }
        self._weekly_reports.append(report)
        return report

    def _suggest_next_actions(self) -> list[str]:
        """Suggest next growth actions based on current state."""
        actions = []
        if self._stats["leads_found"] < 10:
            actions.append("Run find-hot-leads on Twitter and LinkedIn to build pipeline")
        if self._stats["leads_found"] > 0 and self._stats["outreach_sent"] < self._stats["leads_found"] * 0.5:
            actions.append("Run outreach campaigns — you have uncontacted leads")
        if self._stats["outreach_sent"] > 5 and self._stats["demos_scheduled"] == 0:
            actions.append("Review outreach templates — try different angles or channels")
        if self._stats["deals_closed"] == 0 and self._stats["demos_scheduled"] > 0:
            actions.append("Follow up on demo leads — send proposals")
        if len(self._weekly_reports) == 0:
            actions.append("Post content on Twitter and LinkedIn to build awareness")
        if not actions:
            actions.append("Keep the momentum — run another outreach batch this week")
        return actions
