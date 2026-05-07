/**
 * ReviewState — localStorage helper for per-session review state.
 *
 * State is stored under the key "review-{sessionId}" as a JSON object
 * mapping question IDs to state objects:
 *   { state: "accepted"|"dismissed"|"edited"|"pending", value?, selected_id? }
 *
 * No server round-trips are made. State is written on every interaction.
 */
class ReviewState {
  constructor(sessionId) {
    this._key = "review-" + sessionId;
    this._sessionId = sessionId;
  }

  /** Load full state map from localStorage. Returns {} if missing or corrupt. */
  load() {
    try {
      return JSON.parse(localStorage.getItem(this._key) || "{}");
    } catch (e) {
      return {};
    }
  }

  /** Persist full state map to localStorage. */
  _persist(map) {
    try {
      localStorage.setItem(this._key, JSON.stringify(map));
    } catch (e) {
      // Quota exceeded or private browsing — silently ignore
    }
  }

  /** Save state for a single question (localStorage + server). */
  save(questionId, stateObj) {
    const map = this.load();
    map[questionId] = stateObj;
    this._persist(map);
    fetch("/session/" + this._sessionId + "/review-state/" + encodeURIComponent(questionId), {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      credentials: "same-origin",
      body: JSON.stringify(stateObj)
    }).catch(function() {});
  }

  /** Get state for a single question. Returns null if not saved. */
  get(questionId) {
    return this.load()[questionId] || null;
  }

  /** Merge server state into localStorage. Server keys take precedence. */
  loadWithServer(serverState) {
    var map = this.load();
    for (var qid in serverState) {
      if (serverState.hasOwnProperty(qid)) {
        map[qid] = serverState[qid];
      }
    }
    this._persist(map);
    return map;
  }

  /** Clear all state for this session. */
  clear() {
    try {
      localStorage.removeItem(this._key);
    } catch (e) {}
  }

  /**
   * Restore all saved states on page load.
   * - accepted → pre-fill input, highlight block green
   * - dismissed → hide suggestion block
   * - edited → pre-fill input, mark block as modified
   */
  restoreAll() {
    const map = this.load();
    for (const [questionId, saved] of Object.entries(map)) {
      const block = document.getElementById("sug-" + questionId);
      const textarea = document.getElementById("input-" + questionId);

      if (saved.state === "dismissed") {
        if (block) block.style.display = "none";
      } else if (saved.state === "accepted") {
        if (block) {
          block.style.border = "1px solid #16a34a";
          block.style.background = "#f0fdf4";
        }
        if (textarea && saved.value !== undefined) {
          textarea.value = saved.value;
        } else if (saved.selected_id) {
          const radio = document.getElementById("opt-" + questionId + "-" + saved.selected_id);
          if (radio) radio.checked = true;
        }
      } else if (saved.state === "edited") {
        if (block) {
          block.style.border = "1px solid #2563eb";
          block.style.background = "#eff6ff";
        }
        if (textarea && saved.value !== undefined) {
          textarea.value = saved.value;
        } else if (saved.selected_id) {
          var radio = document.getElementById("opt-" + questionId + "-" + saved.selected_id);
          if (radio) radio.checked = true;
        } else if (saved.selected_ids) {
          saved.selected_ids.forEach(function (id) {
            var cb = document.getElementById("opt-" + questionId + "-" + id);
            if (cb) cb.checked = true;
          });
        }
      }
    }
  }
}

// Auto-track edits on all survey inputs
document.addEventListener("DOMContentLoaded", () => {
  const sessionId = document.querySelector("[data-session-id]")?.dataset.sessionId;
  if (!sessionId) return;
  const rs = new ReviewState(sessionId);

  document.querySelectorAll("textarea[name^='q_'], input[type='range'][name^='q_']").forEach(el => {
    el.addEventListener("input", () => {
      const qid = el.name.replace(/^q_/, "");
      const current = rs.get(qid);
      // Only mark as "edited" if it was previously accepted
      if (current && current.state === "accepted") {
        rs.save(qid, { state: "edited", value: el.value });
      }
    });
  });

  // Track manual changes to radio buttons and checkboxes
  document.querySelectorAll("input[type='radio'][name^='q_'], input[type='checkbox'][name^='q_']").forEach(el => {
    el.addEventListener("change", () => {
      const qid = el.name.replace(/^q_/, "");
      const current = rs.get(qid);
      if (current && current.state === "accepted") {
        if (el.type === "radio") {
          rs.save(qid, { state: "edited", selected_id: el.value });
        } else {
          const checked = Array.from(document.querySelectorAll("input[type='checkbox'][name='q_" + qid + "']:checked"))
            .map(cb => cb.value);
          rs.save(qid, { state: "edited", selected_ids: checked });
        }
        const block = document.getElementById("sug-" + qid);
        if (block) {
          block.style.border = "1px solid #2563eb";
          block.style.background = "#eff6ff";
        }
      }
    });
  });
});
