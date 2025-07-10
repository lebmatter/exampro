// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Exam Settings", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Exam Settings", {
    refresh(frm) {
    },
    
    validate(frm) {
        const domains = frm.doc.restrict_user_account_domains;
        
        // Skip validation if the field is empty
        if (!domains || domains.trim() === '') return;
        
        const domainArray = domains.split(',').map(domain => domain.trim());
        
        // Check each domain format
        const invalidDomains = domainArray.filter(domain => {
            // Domain should not contain @ and should have at least one dot
            return domain.includes('@') || !domain.includes('.') || /\s/.test(domain);
        });
        
        if (invalidDomains.length > 0) {
            frappe.validated = false;
            frappe.msgprint(
                __(`Invalid domain format: ${invalidDomains.join(', ')}. 
                   Please enter domains without @ symbol (e.g. 'company.com, gmail.com').`)
            );
        }
    }
});