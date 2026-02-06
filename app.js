const taskForm = document.getElementById("taskForm");
const taskList = document.getElementById("taskList");
const taskTemplate = document.getElementById("taskTemplate");
const editTemplate = document.getElementById("editTemplate");
const progressCount = document.getElementById("progressCount");
const progressFill = document.getElementById("progressFill");
const emptyState = document.getElementById("emptyState");
const searchInput = document.getElementById("searchInput");
const clearCompleted = document.getElementById("clearCompleted");
const themeToggle = document.getElementById("themeToggle");
const priorityFilter = document.getElementById("priorityFilter");
const sortOrder = document.getElementById("sortOrder");
const statTotal = document.getElementById("statTotal");
const statActive = document.getElementById("statActive");
const statCompleted = document.getElementById("statCompleted");

const STORAGE_KEY = "focusflow.tasks";
const THEME_KEY = "focusflow.theme";

let tasks = [];
let activeFilter = "all";

const loadState = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    tasks = stored ? JSON.parse(stored) : [];
  } catch (error) {
    tasks = [];
  }

  const storedTheme = localStorage.getItem(THEME_KEY);
  if (storedTheme === "dark") {
    document.body.classList.add("dark");
  }
};

const saveState = () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
};

const formatDate = (value) => {
  if (!value) return "No due date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No due date";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
};

const updateProgress = () => {
  const total = tasks.length;
  const completed = tasks.filter((task) => task.completed).length;
  const active = total - completed;
  progressCount.textContent = `${completed} of ${total} complete`;
  const percentage = total === 0 ? 0 : Math.round((completed / total) * 100);
  progressFill.style.width = `${percentage}%`;
  emptyState.style.display = total === 0 ? "block" : "none";
  statTotal.textContent = total;
  statActive.textContent = active;
  statCompleted.textContent = completed;
};

const matchesSearch = (task, term) => {
  if (!term) return true;
  const text = `${task.title} ${task.notes} ${task.tag}`.toLowerCase();
  return text.includes(term.toLowerCase());
};

const comparePriority = (task) => {
  if (task.priority === "high") return 3;
  if (task.priority === "medium") return 2;
  return 1;
};

const sortTasks = (list) => {
  const sortValue = sortOrder.value;
  const sorted = [...list];

  if (sortValue === "due") {
    sorted.sort((a, b) => {
      const dateA = a.dueDate ? new Date(a.dueDate).getTime() : Infinity;
      const dateB = b.dueDate ? new Date(b.dueDate).getTime() : Infinity;
      return dateA - dateB;
    });
    return sorted;
  }

  if (sortValue === "priority") {
    sorted.sort((a, b) => comparePriority(b) - comparePriority(a));
    return sorted;
  }

  sorted.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  return sorted;
};

const getFilteredTasks = () => {
  const searchTerm = searchInput.value.trim().toLowerCase();
  const priorityValue = priorityFilter.value;
  const filtered = tasks.filter((task) => {
    const matchesFilter =
      activeFilter === "all" ||
      (activeFilter === "active" && !task.completed) ||
      (activeFilter === "completed" && task.completed);
    const matchesPriority =
      priorityValue === "all" || task.priority === priorityValue;
    return matchesFilter && matchesPriority && matchesSearch(task, searchTerm);
  });

  return sortTasks(filtered);
};

const renderTasks = () => {
  taskList.innerHTML = "";
  const filtered = getFilteredTasks();

  filtered.forEach((task) => {
    const node = taskTemplate.content.cloneNode(true);
    const item = node.querySelector(".task");
    const checkbox = node.querySelector(".checkbox");
    const title = node.querySelector(".task-title");
    const notes = node.querySelector(".task-notes");
    const priorityBadge = node.querySelector(".badge.priority");
    const dueBadge = node.querySelector(".badge.due");
    const tagBadge = node.querySelector(".badge.tag");
    const editButton = node.querySelector(".edit");
    const deleteButton = node.querySelector(".delete");

    title.textContent = task.title;
    notes.textContent = task.notes || "No additional notes";
    priorityBadge.textContent = `${task.priority} priority`;
    priorityBadge.classList.add(task.priority);
    dueBadge.textContent = formatDate(task.dueDate);
    if (task.dueDate) {
      const dueDate = new Date(task.dueDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      dueDate.setHours(0, 0, 0, 0);
      if (dueDate < today && !task.completed) {
        dueBadge.classList.add("overdue");
      }
    }
    tagBadge.textContent = task.tag || "General";

    if (task.completed) {
      item.classList.add("completed");
      checkbox.setAttribute("aria-pressed", "true");
    }

    checkbox.addEventListener("click", () => toggleTask(task.id));
    deleteButton.addEventListener("click", () => deleteTask(task.id));
    editButton.addEventListener("click", () => startEdit(item, task));

    taskList.appendChild(node);
  });

  updateProgress();
};

const resetForm = () => {
  taskForm.reset();
  document.getElementById("taskPriority").value = "medium";
};

const addTask = (event) => {
  event.preventDefault();
  const title = document.getElementById("taskTitle").value.trim();
  if (!title) return;

  const newTask = {
    id: crypto.randomUUID(),
    title,
    notes: document.getElementById("taskNotes").value.trim(),
    dueDate: document.getElementById("taskDue").value,
    priority: document.getElementById("taskPriority").value,
    tag: document.getElementById("taskTag").value.trim(),
    completed: false,
    createdAt: new Date().toISOString(),
  };

  tasks.unshift(newTask);
  saveState();
  renderTasks();
  resetForm();
};

const toggleTask = (id) => {
  tasks = tasks.map((task) =>
    task.id === id ? { ...task, completed: !task.completed } : task
  );
  saveState();
  renderTasks();
};

const deleteTask = (id) => {
  tasks = tasks.filter((task) => task.id !== id);
  saveState();
  renderTasks();
};

const startEdit = (item, task) => {
  if (item.querySelector(".edit-form")) return;

  const editNode = editTemplate.content.cloneNode(true);
  const form = editNode.querySelector(".edit-form");
  const titleInput = editNode.querySelector(".edit-title");
  const notesInput = editNode.querySelector(".edit-notes");
  const dueInput = editNode.querySelector(".edit-due");
  const prioritySelect = editNode.querySelector(".edit-priority");
  const tagInput = editNode.querySelector(".edit-tag");
  const cancelButton = editNode.querySelector(".cancel");

  titleInput.value = task.title;
  notesInput.value = task.notes;
  dueInput.value = task.dueDate;
  prioritySelect.value = task.priority;
  tagInput.value = task.tag;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    tasks = tasks.map((existing) =>
      existing.id === task.id
        ? {
            ...existing,
            title: titleInput.value.trim(),
            notes: notesInput.value.trim(),
            dueDate: dueInput.value,
            priority: prioritySelect.value,
            tag: tagInput.value.trim(),
          }
        : existing
    );
    saveState();
    renderTasks();
  });

  cancelButton.addEventListener("click", () => renderTasks());

  item.innerHTML = "";
  item.appendChild(form);
};

const setFilter = (filter) => {
  activeFilter = filter;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.filter === filter);
  });
  renderTasks();
};

const clearDone = () => {
  tasks = tasks.filter((task) => !task.completed);
  saveState();
  renderTasks();
};

const toggleTheme = () => {
  document.body.classList.toggle("dark");
  const theme = document.body.classList.contains("dark") ? "dark" : "light";
  localStorage.setItem(THEME_KEY, theme);
};

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => setFilter(tab.dataset.filter));
});

searchInput.addEventListener("input", renderTasks);
clearCompleted.addEventListener("click", clearDone);
taskForm.addEventListener("submit", addTask);
themeToggle.addEventListener("click", toggleTheme);
priorityFilter.addEventListener("change", renderTasks);
sortOrder.addEventListener("change", renderTasks);

loadState();
renderTasks();
