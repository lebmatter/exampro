function initiatePayment(scheduleName) {
  var btn = document.getElementById("pay-btn");
  btn.disabled = true;
  btn.textContent = "Processing…";

  frappe.call({
    method: "exampro.exam_pro.api.payment.create_razorpay_order",
    args: { schedule_name: scheduleName },
    callback: function (r) {
      if (!r.message) {
        btn.disabled = false;
        btn.innerHTML =
          '<i data-feather="credit-card"></i>Pay ₹' + r.message?.amount;
        if (typeof feather !== "undefined") feather.replace();
        frappe.msgprint("Failed to create payment order. Please try again.");
        return;
      }

      var data = r.message;
      var options = {
        key: data.key_id,
        amount: data.amount,
        currency: data.currency,
        name: "ExamPro",
        description: data.exam_title,
        order_id: data.order_id,
        handler: function (response) {
          verifyPayment(
            scheduleName,
            response.razorpay_order_id,
            response.razorpay_payment_id,
            response.razorpay_signature
          );
        },
        modal: {
          ondismiss: function () {
            btn.disabled = false;
            btn.innerHTML =
              '<i data-feather="credit-card"></i>Pay ₹' +
              Math.round(data.amount / 100);
            if (typeof feather !== "undefined") feather.replace();
          },
        },
        prefill: {
          email: frappe.session.user,
        },
      };

      var rzp = new Razorpay(options);
      rzp.open();
    },
    error: function () {
      btn.disabled = false;
      btn.innerHTML = '<i data-feather="credit-card"></i>Retry Payment';
      if (typeof feather !== "undefined") feather.replace();
    },
  });
}

function verifyPayment(
  scheduleName,
  razorpayOrderId,
  razorpayPaymentId,
  razorpaySignature
) {
  frappe.call({
    method: "exampro.exam_pro.api.payment.verify_payment",
    args: {
      schedule_name: scheduleName,
      razorpay_order_id: razorpayOrderId,
      razorpay_payment_id: razorpayPaymentId,
      razorpay_signature: razorpaySignature,
    },
    callback: function (r) {
      if (r.message && r.message.success) {
        frappe.msgprint({
          title: "Success",
          message: "Payment verified! Redirecting to dashboard…",
          indicator: "green",
        });
        setTimeout(function () {
          window.location.href = "/dashboard";
        }, 1500);
      } else {
        frappe.msgprint({
          title: "Error",
          message: "Payment verification failed. Please contact support.",
          indicator: "red",
        });
      }
    },
    error: function () {
      frappe.msgprint({
        title: "Error",
        message:
          "Payment verification failed. If you were charged, please contact support.",
        indicator: "red",
      });
    },
  });
}

function registerFree(scheduleName) {
  var btn = document.getElementById("register-btn");
  btn.disabled = true;
  btn.textContent = "Registering…";

  frappe.call({
    method: "exampro.exam_pro.api.payment.register_for_free",
    args: { schedule_name: scheduleName },
    callback: function (r) {
      if (r.message && r.message.success) {
        frappe.msgprint({
          title: "Success",
          message: "Registration complete! Redirecting to dashboard…",
          indicator: "green",
        });
        setTimeout(function () {
          window.location.href = "/dashboard";
        }, 1500);
      } else {
        btn.disabled = false;
        btn.innerHTML =
          '<i data-feather="check-circle"></i>Register';
        if (typeof feather !== "undefined") feather.replace();
        frappe.msgprint({
          title: "Error",
          message: "Registration failed. Please try again.",
          indicator: "red",
        });
      }
    },
    error: function () {
      btn.disabled = false;
      btn.innerHTML =
        '<i data-feather="check-circle"></i>Register';
      if (typeof feather !== "undefined") feather.replace();
    },
  });
}
