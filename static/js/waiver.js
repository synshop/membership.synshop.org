// Shared by /new and the /update waiver gate (templates/_waiver_card.html).
// Online signing is for adults only; minors sign the paper waiver with a
// parent or guardian. The server repeats these checks in synshop/waiver.py.

// Returns true if #waiverDob holds a valid adult date of birth, showing the
// matching .invalid-feedback message otherwise
function checkWaiverDob() {
  const dob = new Date($("#waiverDob").val() + "T00:00:00");
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  if (today.getMonth() < dob.getMonth() ||
      (today.getMonth() == dob.getMonth() && today.getDate() < dob.getDate())) {
    age--;
  }

  $("#waiver-dob-invalid").hide();
  $("#waiver-dob-minor").hide();
  if (isNaN(age) || dob > today || age > 120) {
    $("#waiver-dob-invalid").show();
    return false;
  } else if (age < 18) {
    $("#waiver-dob-minor").show();
    return false;
  }
  return true;
}

// The Month / Day / Year selects fill the hidden #waiverDob input (YYYY-MM-DD)
// and fire its change event, so pages can listen on #waiverDob alone
$(function() {
  const thisYear = new Date().getFullYear();
  for (let y = thisYear; y >= thisYear - 120; y--) {
    $("#waiverDobYear").append($("<option>").val(y).text(y));
  }

  $("#waiverDobMonth, #waiverDobDay, #waiverDobYear").on("change", function() {
    const y = $("#waiverDobYear").val(), m = $("#waiverDobMonth").val(), d = $("#waiverDobDay").val();
    const hadValue = $("#waiverDob").val() !== "";

    // Leave the value empty until all three are picked and form a real date
    // (no February 31st)
    let value = "";
    if (y && m && d) {
      const dt = new Date(y, m - 1, d);
      if (dt.getMonth() == m - 1) {
        value = y + "-" + String(m).padStart(2, "0") + "-" + String(d).padStart(2, "0");
      }
    }
    $("#waiverDob").val(value);

    // Don't flag a half-picked date; check once all three are chosen
    if ((y && m && d) || hadValue) {
      $("#waiverDob").trigger("change");
    }
  });
});

// Returns true if a signature has been typed, showing the error otherwise
function checkWaiverSignature() {
  if ($("#waiverSignature").val().trim().length === 0) {
    $("#waiver-signature-invalid").show();
    return false;
  }
  $("#waiver-signature-invalid").hide();
  return true;
}
