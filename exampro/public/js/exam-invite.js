function acceptInvitation(scheduleName) {
  var $btn = $("#accept-invite");
  $btn
    .prop("disabled", true)
    .html('<i class="bi bi-arrow-repeat mr-2"></i>Processing...');

  frappe.call({
    method: "exampro.www.exam.invite.accept_invitation",
    args: {
      schedule_name: scheduleName,
    },
    callback: function (r) {
      if (r.message && r.message.success) {
        frappe.show_alert({
          message: r.message.message,
          indicator: "green",
        });
        setTimeout(function () {
          window.location.href = "/my-exams";
        }, 1500);
      } else {
        $btn
          .prop("disabled", false)
          .html('<i class="bi bi-check-circle mr-2"></i>Accept Invitation');
        frappe.show_alert({
          message: r.message
            ? r.message.message
            : "Something went wrong. Please try again.",
          indicator: "red",
        });
      }
    },
  });
}