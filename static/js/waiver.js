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

// Returns true if a signature has been typed, showing the error otherwise
function checkWaiverSignature() {
  if ($("#waiverSignature").val().trim().length === 0) {
    $("#waiver-signature-invalid").show();
    return false;
  }
  $("#waiver-signature-invalid").hide();
  return true;
}
