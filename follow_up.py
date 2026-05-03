from argparse import ArgumentParser
from datetime import datetime
import os
from pathlib import Path

from bot.follow_up import (
    ACTION_STATUSES,
    DEFAULT_FOLLOW_UP_QUEUE_PATH,
    approve_follow_up_action,
    build_follow_up_actions,
    build_follow_up_brief,
    cleanup_follow_up_backlog,
    daily_plan_date_for_path,
    discover_follow_up_targets,
    find_latest_daily_plan,
    list_follow_up_actions,
    load_daily_plan,
    load_posts_for_plan,
    load_publish_records,
    mark_follow_up_action_sent,
    merge_follow_up_actions,
    skip_follow_up_action,
    write_follow_up_brief,
)
from bot.follow_up_executor import execute_approved_actions
from bot.follow_up_session import (
    DEFAULT_FOLLOW_UP_SESSION_STATE_PATH,
    run_follow_up_session,
)


def load_env_file(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


def main():
    parser = ArgumentParser(description="Write a post-publish ShirtClawd follow-up brief.")
    parser.add_argument("--date", default=None)
    parser.add_argument("--plan", default=None)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--log-dir", default="data")
    parser.add_argument("--queue", default=str(DEFAULT_FOLLOW_UP_QUEUE_PATH))
    parser.add_argument("--session-state", default=str(DEFAULT_FOLLOW_UP_SESSION_STATE_PATH))
    parser.add_argument("--uptime-minutes", type=int, default=60)
    parser.add_argument("--daily-session", action="store_true", help="Run one catch-up session: refresh to-dos, check inbox, optionally execute approved actions, then exit.")
    parser.add_argument("--session-execute-approved", action="store_true", help="During --daily-session, execute currently approved API-safe actions.")
    parser.add_argument("--inbox-limit", type=int, default=50, help="Maximum Bluesky notifications to inspect during --daily-session.")
    parser.add_argument("--inbox-lookback-hours", type=int, default=24, help="Fallback inbox lookback when there is no saved session state.")
    parser.add_argument("--list-actions", action="store_true")
    parser.add_argument("--status", choices=ACTION_STATUSES, default=None)
    parser.add_argument("--approve", metavar="ACTION_ID", default=None)
    parser.add_argument("--mark-sent", metavar="ACTION_ID", default=None)
    parser.add_argument("--skip", metavar="ACTION_ID", default=None)
    parser.add_argument("--copy", default=None, help="Final approved copy for an action.")
    parser.add_argument("--target-url", default=None, help="Target post/account URL for an action.")
    parser.add_argument("--external-id", default=None, help="Platform ID or URL after an action is sent.")
    parser.add_argument("--note", default=None)
    parser.add_argument("--execute-approved", action="store_true")
    parser.add_argument("--cleanup-backlog", action="store_true", help="Skip stale or duplicate manual/unsupported pending actions.")
    parser.add_argument("--carryover-max-days", type=int, default=1, help="Manual carryover days to keep during --cleanup-backlog.")
    parser.add_argument("--publish", action="store_true", help="Actually execute approved actions. Without this, execution is a dry run.")
    parser.add_argument("--platform", default=None, help="Restrict execution to one platform, e.g. bluesky.")
    parser.add_argument("--action-id", default=None, help="Restrict execution to one action ID.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--latest-plan", action="store_true", help="If the requested daily plan is missing, use the latest workflow plan in the output directory.")
    parser.add_argument("--skip-target-discovery", action="store_true", help="Do not search Bluesky for candidate reply targets.")
    parser.add_argument("--target-candidates", type=int, default=3, help="Candidate Bluesky targets to attach per planned Bluesky post.")
    parser.add_argument("--target-search-limit", type=int, default=20, help="Bluesky search results to inspect per discovery query.")
    parser.add_argument("--target-max-age-days", type=int, default=21, help="Oldest Bluesky candidate post age to consider.")
    parser.add_argument("--automation-only", action="store_true", help="Only queue follow-up actions that have API-executable targets.")
    args = parser.parse_args()

    requested_date = args.date or datetime.now().date().isoformat()
    if args.daily_session:
        requested_date, plan_path = resolve_plan_request(args, requested_date)
        result = run_follow_up_session(
            run_date=requested_date,
            plan_path=plan_path,
            output_dir=Path(args.output_dir),
            log_dir=Path(args.log_dir),
            queue_path=Path(args.queue),
            state_path=Path(args.session_state),
            uptime_minutes=args.uptime_minutes,
            skip_target_discovery=args.skip_target_discovery,
            target_candidates=args.target_candidates,
            target_search_limit=args.target_search_limit,
            target_max_age_days=args.target_max_age_days,
            inbox_limit=args.inbox_limit,
            inbox_lookback_hours=args.inbox_lookback_hours,
            execute_approved=args.session_execute_approved,
            publish=args.publish,
            execute_platform=args.platform,
            execute_limit=args.limit if args.limit is not None else 3,
            automation_only=args.automation_only,
        )
        print_session_result(result)
        return
    if args.execute_approved:
        results = execute_approved_actions(
            queue_path=args.queue,
            dry_run=not args.publish,
            platform=args.platform,
            action_id=args.action_id,
            limit=args.limit,
            run_date=requested_date,
        )
        print_execution_results(results)
        return
    if args.cleanup_backlog:
        summary = cleanup_follow_up_backlog(
            path=args.queue,
            reference_date=requested_date,
            max_carryover_days=args.carryover_max_days,
        )
        print(
            "Cleaned follow-up backlog: "
            f"{summary.get('skipped_duplicate_count', 0)} duplicate(s), "
            f"{summary.get('skipped_stale_count', 0)} stale action(s) skipped."
        )
        return
    if args.list_actions:
        print_actions(list_follow_up_actions(args.queue, run_date=args.date, status=args.status))
        return
    if args.approve:
        try:
            action = approve_follow_up_action(
                args.approve,
                approved_text=args.copy,
                target_url=args.target_url,
                note=args.note,
                path=args.queue,
            )
        except ValueError as exc:
            print(exc)
            raise SystemExit(1) from exc
        print_action_update("Approved", action)
        return
    if args.mark_sent:
        try:
            action = mark_follow_up_action_sent(
                args.mark_sent,
                target_url=args.target_url,
                external_action_id=args.external_id,
                note=args.note,
                path=args.queue,
            )
        except ValueError as exc:
            print(exc)
            raise SystemExit(1) from exc
        print_action_update("Marked sent", action)
        return
    if args.skip:
        try:
            action = skip_follow_up_action(args.skip, note=args.note, path=args.queue)
        except ValueError as exc:
            print(exc)
            raise SystemExit(1) from exc
        print_action_update("Skipped", action)
        return

    requested_date, plan_path = resolve_plan_request(args, requested_date)
    plan = load_daily_plan(plan_path)
    run_date = requested_date
    post_refs = load_posts_for_plan(plan, args.output_dir)
    platforms = [entry.get("platform") for entry in plan.get("planned_posts", []) if entry.get("platform")]
    publish_records = load_publish_records(run_date, args.log_dir, platforms=platforms)
    target_discovery = {}
    if not args.skip_target_discovery:
        target_discovery = discover_follow_up_targets(
            post_refs=post_refs,
            run_date=run_date,
            max_candidates_per_post=args.target_candidates,
            search_limit=args.target_search_limit,
            max_age_days=args.target_max_age_days,
            exclude_handles=[os.getenv("BLUESKY_HANDLE")],
            exclude_threads_usernames=[os.getenv("THREADS_USERNAME"), os.getenv("THREADS_USER_ID")],
        )
    actions = build_follow_up_actions(
        plan=plan,
        post_refs=post_refs,
        publish_records=publish_records,
        run_date=run_date,
        target_discovery=target_discovery,
        automation_only=args.automation_only,
    )
    merge_follow_up_actions(actions, args.queue, replace_run_date=run_date if args.automation_only else None)
    markdown = build_follow_up_brief(
        plan=plan,
        post_refs=post_refs,
        publish_records=publish_records,
        run_date=run_date,
        uptime_minutes=args.uptime_minutes,
        queue_actions=list_follow_up_actions(args.queue, run_date=run_date),
    )
    destination = write_follow_up_brief(markdown, run_date, args.output_dir)
    print(f"Wrote follow-up brief -> {destination}")
    print(f"Queued {len(actions)} follow-up actions -> {args.queue}")
    print_discovery_summary(target_discovery)


def resolve_plan_request(args, requested_date):
    plan_path = Path(args.plan) if args.plan else Path(args.output_dir) / f"daily_plan_{requested_date}.json"
    if args.latest_plan and not args.plan and not plan_path.exists():
        latest_plan_path = find_latest_daily_plan(args.output_dir, by_mtime=True)
        if latest_plan_path:
            latest_plan_date = daily_plan_date_for_path(latest_plan_path) or requested_date
            print(
                f"No daily plan found for {requested_date}; "
                f"using latest workflow plan {latest_plan_path} ({latest_plan_date})."
            )
            return latest_plan_date, latest_plan_path
    if not args.date:
        plan_date = daily_plan_date_for_path(plan_path)
        if plan_date:
            return plan_date, plan_path
    return requested_date, plan_path


def print_actions(actions):
    if not actions:
        print("No follow-up actions found.")
        return
    for action in actions:
        target = action.get("target_url") or action.get("target_type") or action.get("platform") or ""
        text = action.get("approved_text") or action.get("draft_text") or ""
        print(
            f"{action.get('action_id')} [{action.get('status')}] "
            f"{action.get('kind')} -> {target}: {text}"
        )


def print_action_update(label, action):
    print(f"{label} {action.get('action_id')} [{action.get('status')}]")


def print_execution_results(results):
    if not results:
        print("No approved follow-up actions matched.")
        return
    for result in results:
        status = result.get("status")
        action_id = result.get("action_id")
        detail = result.get("external_action_id") or result.get("reason") or result.get("target_url") or ""
        print(f"{action_id} [{status}] {detail}")


def print_discovery_summary(target_discovery):
    if not target_discovery:
        return
    candidate_count = sum(len(result.get("candidates", [])) for result in target_discovery.values())
    error_count = sum(1 for result in target_discovery.values() if result.get("error"))
    if candidate_count:
        print(f"Discovered {candidate_count} candidate targets.")
    if error_count:
        print(f"Discovery unavailable for {error_count} planned post(s); see the follow-up brief.")


def print_session_result(result):
    print(f"Wrote follow-up brief -> {result.get('follow_up_brief_path')}")
    print(f"Wrote session report -> {result.get('session_report_path')}")
    print(f"Updated queue -> {result.get('queue_path')}")
    print(f"Checked inbox since {result.get('checked_since')}")
    print(
        "Queued "
        f"{result.get('planned_action_count', 0)} planned actions and "
        f"{result.get('inbox_action_count', 0)} inbox action(s)."
    )
    if result.get("suppressed_planned_action_count"):
        print(f"Suppressed {result.get('suppressed_planned_action_count')} manual-only planned action(s).")
    if result.get("inbox_error"):
        print(f"Bluesky inbox unavailable: {result.get('inbox_error')}")
    execution_results = result.get("execution_results") or []
    if execution_results:
        print_execution_results(execution_results)


if __name__ == "__main__":
    main()
