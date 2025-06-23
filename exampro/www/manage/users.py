import frappe
from frappe import _

import frappe
from frappe import _
from frappe.utils import validate_email_address

@frappe.whitelist()
def update_user_role(user, role, action):
    """
    Update a user's role (add or remove)
    
    Args:
        user (str): User email or name
        role (str): Role to add or remove (Candidate, Proctor, Evaluator)
        action (str): 'add' or 'remove'
    """
    if not frappe.has_permission("User", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Validate role
        if role not in ["Candidate", "Proctor", "Evaluator"]:
            return {"success": False, "error": _("Invalid role")}
        
        # Format role name according to application standards
        role_name = f"Exam {role}"
        
        user_doc = frappe.get_doc("User", user)
        
        # Check if role already exists for user
        has_role = False
        for r in user_doc.roles:
            if r.role == role_name:
                has_role = True
                break
        
        if action == "add" and not has_role:
            # Add role
            user_doc.append("roles", {"role": role_name})
            user_doc.save(ignore_permissions=True)
            frappe.db.commit()
            return {"success": True}
            
        elif action == "remove" and has_role:
            # Remove role
            roles = [r for r in user_doc.roles if r.role != role_name]
            user_doc.roles = roles
            user_doc.save(ignore_permissions=True)
            frappe.db.commit()
            return {"success": True}
            
        else:
            # No change needed
            return {"success": True}
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error updating role for {user}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def add_users(emails, role):
    """
    Add new users and assign the specified role
    
    Args:
        emails (str): Comma-separated list of email addresses
        role (str): Role to assign (Candidate, Proctor, Evaluator)
    """
    if not frappe.has_permission("User", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Validate role
        if role not in ["Candidate", "Proctor", "Evaluator"]:
            return {"success": False, "error": _("Invalid role")}
        
        # Format role name according to application standards
        role_name = f"Exam {role}"
        
        # Parse emails
        email_list = [email.strip() for email in emails.split(',')]
        added_count = 0
        error_count = 0
        errors = []
        
        for email in email_list:
            if not email:
                continue
                
            # Validate email
            try:
                validate_email_address(email)
            except Exception:
                error_count += 1
                errors.append(f"Invalid email: {email}")
                continue
                
            # Check if user already exists
            user_exists = frappe.db.exists("User", {"email": email})
            
            if user_exists:
                user_doc = frappe.get_doc("User", {"email": email})
            else:
                # Create new user
                user_doc = frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": email.split("@")[0],
                    "send_welcome_email": 1,
                    "enabled": 1,
                })
                user_doc.insert(ignore_permissions=True)
            
            # Assign role if not already assigned
            has_role = False
            for r in user_doc.roles:
                if r.role == role_name:
                    has_role = True
                    break
            
            if not has_role:
                user_doc.append("roles", {"role": role_name})
                user_doc.save(ignore_permissions=True)
            
            added_count += 1
        
        frappe.db.commit()
        
        message = f"Added {added_count} users successfully"
        if error_count > 0:
            message += f", {error_count} failed"
            
        return {
            "success": True, 
            "message": message,
            "errors": errors if errors else None
        }
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error adding users")
        return {"success": False, "error": str(e)}


def get_users():
    """Get all users with their role information"""
    
    # Check if user has permission to view Users
    if not frappe.has_permission("User", "read"):
        return []
    
    # Get all Website users (exclude system users)
    users = frappe.get_all(
        "User",
        filters={"user_type": "Website User"},
        fields=["name", "email", "first_name", "last_name"]
    )
    
    # Get role assignments for each user
    for user in users:
        user_roles = frappe.get_all(
            "Has Role",
            filters={"parent": user.name},
            fields=["role"]
        )
        
        role_list = [r.role for r in user_roles]
        
        # Set flags for each role
        user["is_candidate"] = "Exam Candidate" in role_list
        user["is_proctor"] = "Exam Proctor" in role_list
        user["is_evaluator"] = "Exam Evaluator" in role_list
        
    return users

def get_context(context):
    """Setup page context"""
    
    # Redirect guest users to login
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    # Check if user has Exam Manager role
    if not "Exam Manager" in frappe.get_roles(frappe.session.user):
        frappe.throw(_("You are not authorized to access this page"))

    # Set page data
    context.no_cache = 1
    context.users = get_users()
    
    context.metatags = {
        "title": _("Manage Users"),
        "description": "Manage exam system users and their permissions"
    }
