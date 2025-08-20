function downloadCertificate(certificateName) {
  // Show loading state
  const button = event.target.closest("button");
  const originalContent = button.innerHTML;
  button.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Downloading...';
  button.disabled = true;

  // Create a form to submit the download request
  frappe.call({
    method: "exampro.www.my_exams.download_certificate",
    args: {
      certificate_name: certificateName,
    },
    callback: function (r) {
      if (r.message) {
        // Create a temporary link to download the file
        const link = document.createElement("a");
        link.href = "data:application/pdf;base64," + r.message;
        link.download = `certificate_${certificateName}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Show success message
        frappe.show_alert({
          message: "Certificate downloaded successfully!",
          indicator: "green",
        });
      }
    },
    error: function (r) {
      frappe.show_alert({
        message: r.message || "Error downloading certificate",
        indicator: "red",
      });
    },
    always: function () {
      // Restore button state
      button.innerHTML = originalContent;
      button.disabled = false;
    },
  });
}