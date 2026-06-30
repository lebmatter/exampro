function fillTemplate(template, data) {
	return template
		.replace(/{candidate_name}/g, data.candidateName)
		.replace(/{score}/g, data.score)
		.replace(/{max_score}/g, data.maxScore)
		.replace(/{exam_name}/g, data.examName)
		.replace(/{status}/g, data.status);
}

function shareLinkedIn() {
	const text = fillTemplate(SHARE_DATA.linkedinTemplate, SHARE_DATA);
	const url = "https://www.linkedin.com/shareArticle?mini=true"
		+ "&url=" + encodeURIComponent(SHARE_DATA.url)
		+ "&summary=" + encodeURIComponent(text);
	window.open(url, "_blank", "width=600,height=500");
}

function shareX() {
	const text = fillTemplate(SHARE_DATA.xTemplate, SHARE_DATA);
	const url = "https://twitter.com/intent/tweet"
		+ "?text=" + encodeURIComponent(text)
		+ "&url=" + encodeURIComponent(SHARE_DATA.url);
	window.open(url, "_blank", "width=600,height=400");
}
