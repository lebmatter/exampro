// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

const MCQ_HELP_SHOW_OPTIONS = [
	"Do not show",
	"Before question",
	"After wrong answer",
	"After any answer",
];
const NON_MCQ_HELP_SHOW_OPTIONS = [
	"Do not show",
	"Before question",
	"After any answer",
];

function refresh_help_show_options(frm) {
	const options = frm.doc.type === "Choices" ? MCQ_HELP_SHOW_OPTIONS : NON_MCQ_HELP_SHOW_OPTIONS;
	frm.set_df_property("help_show", "options", options.join("\n"));

	if (frm.doc.type !== "Choices" && frm.doc.help_show === "After wrong answer") {
		frm.set_value("help_show", "After any answer");
	}

	frm.refresh_field("help_show");
}

frappe.ui.form.on("Exam Question", {
	refresh(frm) {
		refresh_help_show_options(frm);
	},
	type(frm) {
		refresh_help_show_options(frm);
	},
});
