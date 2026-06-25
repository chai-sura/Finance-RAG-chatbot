"""
permissions.py — the role -> allowed-roles mapping.

A user's role doesn't just grant THAT role's docs — it grants a SET.
e.g. a finance user sees finance AND general docs. C-level sees everything.
This map is the single source of truth for "what can this role retrieve."
"""

# Every department role can also see "general" (the employee handbook),
# because general info is available to everyone. C-level sees all roles.
ALL_ROLES = ["engineering", "finance", "general", "hr", "marketing"]

ROLE_ACCESS = {
    "engineering": ["engineering", "general"],
    "finance":     ["finance", "general"],
    "hr":          ["hr", "general"],
    "marketing":   ["marketing", "general"],
    "c-level":     ALL_ROLES,            # full access
    "employee":    ["general"],          # only general company info
}


def allowed_roles_for(role: str) -> list:
    """Return the list of data-roles a given user-role may retrieve."""
    return ROLE_ACCESS.get(role, ["general"])  # unknown role -> safest default