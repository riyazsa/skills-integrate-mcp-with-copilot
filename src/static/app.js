document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");
  const loginForm = document.getElementById("login-form");
  const logoutButton = document.getElementById("logout-button");
  const forgotPasswordForm = document.getElementById("forgot-password-form");
  const resetPasswordForm = document.getElementById("reset-password-form");
  const profileForm = document.getElementById("profile-form");
  const accountMessageDiv = document.getElementById("account-message");
  const authStatus = document.getElementById("auth-status");

  let authToken = localStorage.getItem("teacherAuthToken") || "";

  function showAccountMessage(text, className = "info") {
    accountMessageDiv.textContent = text;
    accountMessageDiv.className = className;
    accountMessageDiv.classList.remove("hidden");
  }

  function clearAccountMessage() {
    accountMessageDiv.classList.add("hidden");
  }

  function setAuthStatus(text) {
    authStatus.textContent = text;
  }

  function authHeaders() {
    return authToken
      ? {
          Authorization: `Bearer ${authToken}`,
        }
      : {};
  }

  async function loadProfile() {
    if (!authToken) {
      setAuthStatus("Not signed in");
      return;
    }

    try {
      const response = await fetch("/me/profile", {
        headers: {
          ...authHeaders(),
        },
      });

      if (!response.ok) {
        throw new Error("Could not load profile");
      }

      const profile = await response.json();
      document.getElementById("profile-full-name").value = profile.full_name || "";
      document.getElementById("profile-email").value = profile.email || "";
      document.getElementById("profile-phone").value = profile.phone || "";
      document.getElementById("profile-avatar-url").value = profile.avatar_url || "";
      setAuthStatus(`Signed in as ${profile.username}`);
    } catch (error) {
      authToken = "";
      localStorage.removeItem("teacherAuthToken");
      setAuthStatus("Not signed in");
    }
  }

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      const activities = await response.json();

      // Clear loading message
      activitiesList.innerHTML = "";
      activitySelect.innerHTML = '<option value="">-- Select an activity --</option>';

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const spotsLeft =
          details.max_participants - details.participants.length;

        // Create participants HTML with delete icons instead of bullet points
        const participantsHTML =
          details.participants.length > 0
            ? `<div class="participants-section">
              <h5>Participants:</h5>
              <ul class="participants-list">
                ${details.participants
                  .map(
                    (email) =>
                      `<li><span class="participant-email">${email}</span><button class="delete-btn" data-activity="${name}" data-email="${email}">❌</button></li>`
                  )
                  .join("")}
              </ul>
            </div>`
            : `<p><em>No participants yet</em></p>`;

        activityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Schedule:</strong> ${details.schedule}</p>
          <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
          <div class="participants-container">
            ${participantsHTML}
          </div>
        `;

        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });

      // Add event listeners to delete buttons
      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
    } catch (error) {
      activitiesList.innerHTML =
        "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    const button = event.target;
    const activity = button.getAttribute("data-activity");
    const email = button.getAttribute("data-email");

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
        }
      );

      const result = await response.json();

      if (response.ok) {
        messageDiv.textContent = result.message;
        messageDiv.className = "success";

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        messageDiv.textContent = result.detail || "An error occurred";
        messageDiv.className = "error";
      }

      messageDiv.classList.remove("hidden");

      // Hide message after 5 seconds
      setTimeout(() => {
        messageDiv.classList.add("hidden");
      }, 5000);
    } catch (error) {
      messageDiv.textContent = "Failed to unregister. Please try again.";
      messageDiv.className = "error";
      messageDiv.classList.remove("hidden");
      console.error("Error unregistering:", error);
    }
  }

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const activity = document.getElementById("activity").value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/signup?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.ok) {
        messageDiv.textContent = result.message;
        messageDiv.className = "success";
        signupForm.reset();

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        messageDiv.textContent = result.detail || "An error occurred";
        messageDiv.className = "error";
      }

      messageDiv.classList.remove("hidden");

      // Hide message after 5 seconds
      setTimeout(() => {
        messageDiv.classList.add("hidden");
      }, 5000);
    } catch (error) {
      messageDiv.textContent = "Failed to sign up. Please try again.";
      messageDiv.className = "error";
      messageDiv.classList.remove("hidden");
      console.error("Error signing up:", error);
    }
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAccountMessage();

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Sign in failed");
      }

      authToken = result.token;
      localStorage.setItem("teacherAuthToken", authToken);
      showAccountMessage("Signed in successfully", "success");
      await loadProfile();
      loginForm.reset();
    } catch (error) {
      showAccountMessage(error.message || "Sign in failed", "error");
    }
  });

  logoutButton.addEventListener("click", () => {
    authToken = "";
    localStorage.removeItem("teacherAuthToken");
    setAuthStatus("Not signed in");
    profileForm.reset();
    showAccountMessage("Signed out", "info");
  });

  forgotPasswordForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAccountMessage();

    const usernameOrEmail = document.getElementById("username-or-email").value;

    try {
      const response = await fetch("/auth/forgot-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username_or_email: usernameOrEmail }),
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || "Failed to start reset flow");
      }

      let message = result.message;
      if (result.reset_token) {
        message += ` Token: ${result.reset_token}`;
        document.getElementById("reset-token").value = result.reset_token;
      }

      showAccountMessage(message, "info");
      forgotPasswordForm.reset();
    } catch (error) {
      showAccountMessage(error.message || "Failed to start reset flow", "error");
    }
  });

  resetPasswordForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAccountMessage();

    const token = document.getElementById("reset-token").value;
    const newPassword = document.getElementById("new-password").value;

    try {
      const response = await fetch("/auth/reset-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || "Password reset failed");
      }

      showAccountMessage(result.message, "success");
      resetPasswordForm.reset();
    } catch (error) {
      showAccountMessage(error.message || "Password reset failed", "error");
    }
  });

  profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAccountMessage();

    if (!authToken) {
      showAccountMessage("Please sign in first", "error");
      return;
    }

    const payload = {
      full_name: document.getElementById("profile-full-name").value,
      email: document.getElementById("profile-email").value,
      phone: document.getElementById("profile-phone").value,
      avatar_url: document.getElementById("profile-avatar-url").value,
    };

    try {
      const response = await fetch("/me/profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify(payload),
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || "Failed to save profile");
      }

      setAuthStatus(`Signed in as ${result.username}`);
      showAccountMessage("Profile updated", "success");
    } catch (error) {
      showAccountMessage(error.message || "Failed to save profile", "error");
    }
  });

  // Initialize app
  fetchActivities();
  loadProfile();
});
