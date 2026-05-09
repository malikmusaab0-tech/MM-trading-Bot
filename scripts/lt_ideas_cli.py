"""
Simple CLI to:
- List pending long-term ideas
- Approve selected ones
"""

from tabulate import tabulate  # pip install tabulate

from data.database import get_session, LongTermIdea


def list_pending():
    with get_session() as session:
        ideas = (
            session.query(LongTermIdea)
            .filter(
                LongTermIdea.executed == False,  # noqa: E712
            )
            .order_by(LongTermIdea.approved.desc(),
                      LongTermIdea.multibagger_score.desc())
            .all()
        )
        return ideas


def main():
    ideas = list_pending()
    if not ideas:
        print("No long-term ideas in the system.")
        return

    rows = []
    for idea in ideas:
        rows.append(
            [
                idea.id,
                "Y" if idea.approved else "N",
                idea.symbol,
                idea.action,
                idea.qty,
                f"{idea.entry_price:.2f}",
                f"{idea.target_price:.2f}",
                f"{idea.upside_pct:.1f}",
                f"{idea.multibagger_score:.1f}",
            ]
        )

    headers = [
        "ID",
        "Approved",
        "Symbol",
        "Action",
        "Qty",
        "Entry",
        "Target",
        "Upside%",
        "MB Score",
    ]
    print(tabulate(rows, headers=headers, tablefmt="github"))

    ids_str = input(
        "\nEnter idea IDs to toggle approval (comma-separated, blank = none): "
    ).strip()
    if not ids_str:
        return

    ids = []
    for part in ids_str.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            print(f"Skipping invalid ID: {part}")

    if not ids:
        return

    with get_session() as session:
        for idea_id in ids:
            idea = session.query(LongTermIdea).get(idea_id)
            if not idea:
                print(f"ID {idea_id} not found.")
                continue
            idea.approved = not idea.approved
            print(
                f"ID {idea.id} ({idea.symbol} {idea.action}) "
                f"approved={idea.approved}"
            )


if __name__ == "__main__":
    main()