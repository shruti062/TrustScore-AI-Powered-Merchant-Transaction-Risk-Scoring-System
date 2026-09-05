
import pandas as pd
import database
import model as risk_model


def retrain_with_feedback():
    """
    Runs the retraining process and returns a small summary dict —
    used both by the CLI entry point and the admin API endpoint.
    """
    feedback_rows = database.get_all_feedback()

    if not feedback_rows:
        risk_model.train_and_save_model()
        return {
            "feedback_used": 0,
            "message": "No feedback collected yet — retrained on original data only.",
        }

    df = pd.read_csv("transactions.csv")

    # A later verdict for the same txn_id overrides an earlier one,
    # since dict keys are unique — iterating in insertion order means
    # the most recent feedback naturally wins.
    verdict_map = {row["txn_id"]: row["verdict"] for row in feedback_rows}

    updated_count = 0
    for txn_id, verdict in verdict_map.items():
        label = 1 if verdict == "confirmed_fraud" else 0
        if txn_id in df["txn_id"].values:
            df.loc[df["txn_id"] == txn_id, "is_fraud"] = label
            updated_count += 1

    df.to_csv("transactions_with_feedback.csv", index=False)
    risk_model.train_and_save_model(csv_path="transactions_with_feedback.csv")

    return {
        "feedback_used": len(feedback_rows),
        "labels_updated": updated_count,
        "message": f"Retrained using {updated_count} feedback-confirmed labels.",
    }


if __name__ == "__main__":
    result = retrain_with_feedback()
    print(result["message"])
