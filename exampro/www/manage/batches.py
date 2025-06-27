import frappe
from frappe import _

@frappe.whitelist()
def create_batch(batch_name):
    """
    Create a new exam batch
    
    Args:
        batch_name (str): Name for the new batch
    """
    if not frappe.has_permission("Exam Batch", "create"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Check if batch already exists
        if frappe.db.exists("Exam Batch", batch_name):
            return {"success": False, "error": _("A batch with this name already exists")}
        
        # Create new batch
        batch = frappe.new_doc("Exam Batch")
        batch.batch_name = batch_name
        batch.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def delete_batch(batch_name):
    """
    Delete an exam batch
    
    Args:
        batch_name (str): Name of the batch to delete
    """
    if not frappe.has_permission("Exam Batch", "delete"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Delete associated batch users first
        batch_users = frappe.get_all("Exam Batch User", filters={"exam_batch": batch_name})
        for user in batch_users:
            frappe.delete_doc("Exam Batch User", user.name, ignore_permissions=True)
        
        # Delete the batch
        frappe.delete_doc("Exam Batch", batch_name, ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_all_batches_with_user_assignments(user):
    """
    Get all batches and whether the user is assigned to them
    
    Args:
        user (str): User email
    """
    if not frappe.has_permission("Exam Batch", "read"):
        return []
    
    try:
        # Get all batches
        all_batches = frappe.get_all("Exam Batch", fields=["name"])
        
        # Get user's batch assignments
        user_batches = frappe.get_all(
            "Exam Batch User", 
            filters={"user": user},
            fields=["exam_batch"]
        )
        
        user_batch_names = [ub.exam_batch for ub in user_batches]
        
        # Add is_member flag to each batch
        for batch in all_batches:
            batch["is_member"] = batch.name in user_batch_names
            
        return all_batches
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Error getting batch data for user {user}")
        return []

@frappe.whitelist()
def update_user_batch_assignments(user, assignments):
    """
    Update a user's batch assignments
    
    Args:
        user (str): User email
        assignments (list): List of dict with batch name and is_member flag
    """
    if not frappe.has_permission("Exam Batch User", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        assignments = frappe.parse_json(assignments)
        
        for assignment in assignments:
            batch_name = assignment.get("batch")
            is_member = assignment.get("is_member")
            
            # Check if user is already in this batch
            existing = frappe.get_all(
                "Exam Batch User",
                filters={"user": user, "exam_batch": batch_name}
            )
            
            if is_member and not existing:
                # Add user to batch
                batch_user = frappe.new_doc("Exam Batch User")
                batch_user.exam_batch = batch_name
                batch_user.user = user
                batch_user.insert(ignore_permissions=True)
            
            elif not is_member and existing:
                # Remove user from batch
                for entry in existing:
                    frappe.delete_doc("Exam Batch User", entry.name, ignore_permissions=True)
        
        frappe.db.commit()
        return {"success": True}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error updating batch assignments for user {user}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_batch_users(batch_name):
    """
    Get all users in a batch
    
    Args:
        batch_name (str): Name of the batch
    """
    if not frappe.has_permission("Exam Batch", "read"):
        return []
    
    batch_users = frappe.get_all(
        "Exam Batch User", 
        filters={"exam_batch": batch_name}, 
        fields=["candidate"]
    )
    
    users = []
    for batch_user in batch_users:
        user = frappe.get_doc("User", batch_user.candidate)
        users.append({
            "name": user.name,
            "email": user.email,
            "full_name": user.full_name or f"{user.first_name} {user.last_name}"
        })
    
    return users

@frappe.whitelist()
def get_available_users(batch_name):
    """
    Get users that are not in the specified batch
    
    Args:
        batch_name (str): Name of the batch
    """
    if not frappe.has_permission("User", "read"):
        return []
    
    # Get users already in the batch
    batch_users = frappe.get_all(
        "Exam Batch User", 
        filters={"exam_batch": batch_name}, 
        pluck="candidate"
    )
    
    # Get all candidate users not in this batch
    candidate_role = frappe.db.get_value("Role", {"role_name": "Exam Candidate"}, "name")
    
    # Get users with Candidate role that are not in the batch
    users = []
    if candidate_role:
        user_roles = frappe.get_all(
            "Has Role",
            filters={
                "role": candidate_role,
                "parent": ["not in", batch_users]
            },
            fields=["parent"]
        )
        
        for user_role in user_roles:
            user = frappe.get_doc("User", user_role.parent)
            if user.enabled:  # Only include enabled users
                users.append({
                    "name": user.name,
                    "email": user.email,
                    "full_name": user.full_name or f"{user.first_name} {user.last_name}"
                })
    
    return users

@frappe.whitelist()
def add_users_to_batch(batch_name, users):
    """
    Add users to a batch
    
    Args:
        batch_name (str): Name of the batch
        users (list): List of user emails to add
    """
    if not frappe.has_permission("Exam Batch User", "create"):
        return {"success": False, "error": _("Not permitted")}
    
    if isinstance(users, str):
        import json
        users = json.loads(users)
    
    try:
        for user in users:
            # Check if user is already in batch
            if not frappe.db.exists("Exam Batch User", {"exam_batch": batch_name, "candidate": user}):
                # Add user to batch
                batch_user = frappe.new_doc("Exam Batch User")
                batch_user.exam_batch = batch_name
                batch_user.candidate = user
                batch_user.insert(ignore_permissions=True)
        
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def remove_user_from_batch(batch_name, user):
    """
    Remove a user from a batch
    
    Args:
        batch_name (str): Name of the batch
        user (str): User email to remove
    """
    if not frappe.has_permission("Exam Batch User", "delete"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Find the batch user entry
        batch_user = frappe.get_doc("Exam Batch User", {"exam_batch": batch_name, "candidate": user})
        
        # Delete the entry
        frappe.delete_doc("Exam Batch User", batch_user.name, ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_user_batches(user):
    """
    Get all batches a user belongs to
    
    Args:
        user (str): User email
    """
    if not frappe.has_permission("Exam Batch User", "read"):
        return []
    
    batch_users = frappe.get_all(
        "Exam Batch User", 
        filters={"candidate": user}, 
        fields=["exam_batch"]
    )
    
    batches = [bu.exam_batch for bu in batch_users]
    return batches

@frappe.whitelist()
def get_users_batch_status(batch_name):
    """
    Get all users and their status in a specific batch
    
    Args:
        batch_name (str): Name of the batch
    """
    if not frappe.has_permission("Exam Batch", "read"):
        return []
    
    try:
        # Get all users in the system
        all_users = frappe.get_all("User", 
                                   fields=["name", "email", "full_name"],
                                   filters={"enabled": 1, "name": ["!=", "Administrator"]})
        
        # Get users in this batch
        batch_users = frappe.get_all(
            "Exam Batch User", 
            filters={"exam_batch": batch_name},
            fields=["user"]
        )
        
        batch_user_emails = [bu.user for bu in batch_users]
        
        # Add in_batch flag to each user
        for user in all_users:
            user["in_batch"] = user.name in batch_user_emails
            
        return all_users
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Error getting users for batch {batch_name}")
        return []

@frappe.whitelist()
def update_batch_user_assignments(batch, assignments):
    """
    Update batch user assignments
    
    Args:
        batch (str): Batch name
        assignments (list): List of dict with user email and in_batch flag
    """
    if not frappe.has_permission("Exam Batch User", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        assignments = frappe.parse_json(assignments)
        
        for assignment in assignments:
            user = assignment.get("user")
            in_batch = assignment.get("in_batch")
            
            # Check if user is already in this batch
            existing = frappe.get_all(
                "Exam Batch User",
                filters={"user": user, "exam_batch": batch}
            )
            
            if in_batch and not existing:
                # Add user to batch
                batch_user = frappe.new_doc("Exam Batch User")
                batch_user.exam_batch = batch
                batch_user.user = user
                batch_user.insert(ignore_permissions=True)
            
            elif not in_batch and existing:
                # Remove user from batch
                for entry in existing:
                    frappe.delete_doc("Exam Batch User", entry.name, ignore_permissions=True)
        
        frappe.db.commit()
        return {"success": True}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error updating user assignments for batch {batch}")
        return {"success": False, "error": str(e)}

def get_context(context):
    if not frappe.has_permission("Exam Batch", "read"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    
    # Get all batches
    batches = []
    batch_docs = frappe.get_all("Exam Batch")
    
    for batch in batch_docs:
        # Count users in batch
        user_count = frappe.db.count("Exam Batch User", {"exam_batch": batch.name})
        
        batches.append({
            "name": batch.name,
            "user_count": user_count
        })
    
    context.batches = batches
