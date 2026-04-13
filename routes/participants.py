from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import users_collection

participants_bp = Blueprint("participants", __name__)

# ==========================================================
# APPROVE PARTICIPANTS PAGE
# ==========================================================

@participants_bp.route("/approve_participants")
@login_required
def approve_participants():

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "owner":
        flash("Only owner can manage participants.")
        return redirect(url_for("dashboard.dashboard"))

    pending_participants = list(users_collection.find({
        "role": "observer",
        "wallet": {"$ne": None},
        "approved": False
    }))

    approved_participants = list(users_collection.find({
        "role": "participant",
        "approved": True
    }))

    participants = list(users_collection.find({
        "role": "observer",
        "approved": False
    }))

    return render_template(
        "approve_participants.html",
        pending=pending_participants,
        approved=approved_participants,
        pending_count=len(participants),
        rejected_users=[]
    )


# ==========================================================
# APPROVE A PARTICIPANT
# ==========================================================

@participants_bp.route("/approve_participant/<username>", methods=["POST"])
@login_required
def approve_participant(username):

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "owner":
        flash("Only the system owner can approve participants.")
        return redirect(url_for("dashboard.dashboard"))

    users_collection.update_one(
        {"username": username},
        {"$set": {"approved": True, "role": "participant"}}
    )

    flash(f"Participant {username} has been approved!")
    return redirect(url_for("participants.approve_participants"))


# ==========================================================
# REMOVE A PARTICIPANT
# ==========================================================

@participants_bp.route("/remove_participant/<username>", methods=["POST"])
@login_required
def remove_participant(username):

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "owner":
        flash("Only owner can remove participants.")
        return redirect(url_for("dashboard.dashboard"))

    users_collection.update_one(
        {"username": username},
        {
            "$set": {
                "role": "observer",
                "approved": False
            }
        }
    )

    flash(f"{username} removed from participant role.")
    return redirect(url_for("participants.approve_participants"))
