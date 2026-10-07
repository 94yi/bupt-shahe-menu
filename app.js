"use strict";

const $ = (id) => document.getElementById(id);
const REPO = "https://github.com/94yi/bupt-shahe-menu";
const MEAL_NAMES = { breakfast: "早餐", lunch: "午餐", dinner: "晚餐", late: "夜宵" };
let menu = null;
let reviews = [];

function isAddon(dish) {
  return /单点[\s\S]*不送/.test(dish.name);
}

function mealsForWindow(windowItem) {
  const meals = new Set(Object.keys(windowItem.meals));
  if (meals.has("lunch") || meals.has("dinner")) {
    meals.add("lunch");
    meals.add("dinner");
  }
  return Object.keys(MEAL_NAMES).filter((meal) => meals.has(meal));
}

function dishesForMeal(windowItem, meal) {
  if (!windowItem) return [];
  if (windowItem.meals[meal]?.length) return windowItem.meals[meal];
  if (meal === "lunch") return windowItem.meals.dinner || [];
  if (meal === "dinner") return windowItem.meals.lunch || [];
  return [];
}

function mealDescription(windowItem, meal) {
  if (!windowItem.meals[meal]?.length && (meal === "lunch" || meal === "dinner")) {
    return `${MEAL_NAMES[meal]} · 常规菜单，实际供应为准`;
  }
  return `${MEAL_NAMES[meal] || meal} · ${menu.meal_dates?.[meal] || menu.menu_date}`;
}

function recommendationCandidates() {
  if (!menu) return [];
  const canteen = $("canteen").value;
  const windowId = $("window").value;
  const mealFilter = $("meal").value;
  const candidates = [];
  const seen = new Set();
  for (const windowItem of menu.windows) {
    if (canteen && windowItem.canteen !== canteen) continue;
    if (windowId && String(windowItem.id) !== windowId) continue;
    for (const meal of mealsForWindow(windowItem)) {
      const dishes = dishesForMeal(windowItem, meal);
      if (mealFilter && meal !== mealFilter) continue;
      for (const dish of dishes) {
        if (isAddon(dish)) continue;
        const key = `${windowItem.id}:${dish.id ?? dish.name}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const opinions = reviews.filter((item) =>
          item.window_id === windowItem.id &&
          (dish.id != null && item.goods_id === dish.id || item.dish === dish.name));
        const average = opinions.length
          ? opinions.reduce((sum, item) => sum + item.rating, 0) / opinions.length : null;
        candidates.push({ windowItem, meal, dish, average, reviewCount: opinions.length });
      }
    }
  }
  return candidates;
}

function pickFood() {
  const target = $("pick-result");
  target.replaceChildren();
  const candidates = recommendationCandidates();
  if (!candidates.length) {
    target.textContent = "暂无可推荐的菜品，请换个食堂、窗口或餐次。";
    return;
  }
  const weights = candidates.map((item) => item.average == null ? 3 : 1 + item.average);
  let point = Math.random() * weights.reduce((sum, weight) => sum + weight, 0);
  let chosen = candidates[candidates.length - 1];
  for (let index = 0; index < candidates.length; index++) {
    point -= weights[index];
    if (point < 0) { chosen = candidates[index]; break; }
  }
  const title = document.createElement("strong");
  title.textContent = chosen.dish.name;
  const place = document.createElement("span");
  place.textContent = `${chosen.windowItem.canteen} / ${chosen.windowItem.window} · ${mealDescription(chosen.windowItem, chosen.meal)}`;
  const detail = document.createElement("small");
  const price = typeof chosen.dish.price_yuan === "number" ? `¥${chosen.dish.price_yuan}` : "价格未标注";
  const rating = chosen.reviewCount ? ` · 点评 ${chosen.average.toFixed(1)}/5（${chosen.reviewCount} 条）` : " · 暂无点评";
  detail.textContent = `${price}${rating} · 月度菜单，供应以官网为准`;
  target.append(title, place, detail);
}

function option(select, value, label) {
  const item = document.createElement("option");
  item.value = String(value);
  item.textContent = label;
  select.append(item);
}

function reset(select, text) {
  select.replaceChildren();
  option(select, "", text);
  select.disabled = true;
}

function selectedWindow() {
  return menu?.windows.find((item) => String(item.id) === $("window").value);
}

function selectedDish() {
  const windowItem = selectedWindow();
  const dishes = dishesForMeal(windowItem, $("meal").value);
  return dishes.find((item, index) => String(index) === $("dish").value);
}

function renderPreview() {
  const target = $("menu-preview");
  target.replaceChildren();
  const windowItem = selectedWindow();
  if (!windowItem) {
    target.textContent = "选好食堂和窗口后，这里会显示菜品。";
    return;
  }
  const meals = $("meal").value ? [$("meal").value] : mealsForWindow(windowItem);
  for (const meal of meals) {
    const heading = document.createElement("strong");
    heading.textContent = mealDescription(windowItem, meal);
    target.append(heading);
    const dishes = dishesForMeal(windowItem, meal);
    const groups = [
      ["推荐菜品", dishes.filter((dish) => !isAddon(dish))],
      ["加餐/单点不送的食物", dishes.filter(isAddon)],
    ];
    for (const [label, items] of groups) {
      if (!items.length) continue;
      const category = document.createElement("p");
      category.className = "menu-category";
      category.textContent = label;
      target.append(category);
      const list = document.createElement("ul");
      for (const dish of items) {
        const row = document.createElement("li");
        row.textContent = dish.name;
        if (typeof dish.price_yuan === "number") {
          const price = document.createElement("span");
          price.className = "price";
          price.textContent = `¥${dish.price_yuan}`;
          row.append(price);
        }
        list.append(row);
      }
      target.append(list);
    }
  }
}

function renderReviews() {
  const target = $("recent-reviews");
  target.replaceChildren();
  const windowId = Number($("window").value);
  const relevant = windowId ? reviews.filter((item) => item.window_id === windowId) : reviews;
  const latest = relevant.slice().sort((a, b) => b.visit_date.localeCompare(a.visit_date)).slice(0, 8);
  if (!latest.length) {
    target.textContent = "暂无点评。";
    return;
  }
  for (const item of latest) {
    const article = document.createElement("article");
    article.className = "review";
    const title = document.createElement("strong");
    title.textContent = `${item.dish} · ${"★".repeat(item.rating)}${"☆".repeat(5 - item.rating)}`;
    const context = document.createElement("small");
    context.textContent = `${item.canteen} / ${item.window} · ${item.visit_date}`;
    const body = document.createElement("p");
    body.textContent = item.comment;
    article.append(title, context, body);
    target.append(article);
  }
}

function updateWindows() {
  reset($("window"), "选择窗口");
  reset($("meal"), "先选窗口");
  reset($("dish"), "先选餐次");
  const canteen = $("canteen").value;
  if (canteen) {
    for (const windowItem of menu.windows.filter((item) => item.canteen === canteen)) {
      option($("window"), windowItem.id, windowItem.window);
    }
    $("window").disabled = false;
  }
  renderPreview();
  renderReviews();
}

function updateMeals() {
  reset($("meal"), "选择餐次");
  reset($("dish"), "先选餐次");
  const windowItem = selectedWindow();
  if (windowItem) {
    for (const meal of mealsForWindow(windowItem)) option($("meal"), meal, MEAL_NAMES[meal] || meal);
    $("meal").disabled = false;
  }
  renderPreview();
  renderReviews();
}

function updateDishes() {
  reset($("dish"), "选择菜品");
  const windowItem = selectedWindow();
  const meal = $("meal").value;
  if (windowItem && meal) {
    dishesForMeal(windowItem, meal).forEach((dish, index) => option($("dish"), index, dish.name));
    option($("dish"), "other", "其他菜品（手动填写）");
    $("dish").disabled = false;
  }
  $("manual-dish-label").hidden = true;
  $("manual-dish").required = false;
  renderPreview();
}

async function loadData() {
  try {
    const response = await fetch("data/menu.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("menu unavailable");
    menu = await response.json();
    if (menu.campus !== "沙河" || !Array.isArray(menu.windows) || !menu.windows.length) {
      throw new Error("menu snapshot unavailable");
    }
    const canteens = [...new Set(menu.windows.map((item) => item.canteen))].sort();
    for (const name of canteens) option($("canteen"), name, name);
    $("pick-food").disabled = false;
    $("snapshot-status").textContent = `沙河菜单快照：${menu.menu_date} · ${menu.windows.length} 个窗口 · 每月更新`;
  } catch {
    $("snapshot-status").textContent = "菜单暂时不可用，稍后再试";
    $("menu-preview").textContent = "没有可用的菜单快照。";
    $("review-form").hidden = true;
  }
  try {
    const response = await fetch("reviews.json", { cache: "no-cache" });
    reviews = response.ok ? await response.json() : [];
    if (!Array.isArray(reviews)) reviews = [];
  } catch {
    reviews = [];
  }
  renderReviews();
}

$("canteen").addEventListener("change", updateWindows);
$("window").addEventListener("change", updateMeals);
$("meal").addEventListener("change", updateDishes);
$("dish").addEventListener("change", () => {
  const manual = $("dish").value === "other";
  $("manual-dish-label").hidden = !manual;
  $("manual-dish").required = manual;
});
$("pick-food").addEventListener("click", pickFood);

const today = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
}).format(new Date());
$("visit-date").value = today;
$("visit-date").max = today;

$("review-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!menu || !event.currentTarget.reportValidity()) return;
  const windowItem = selectedWindow();
  const customDish = $("dish").value === "other";
  const dish = customDish ? null : selectedDish();
  const dishName = customDish ? $("manual-dish").value.trim() : dish?.name;
  const comment = $("comment").value.trim();
  if (!windowItem || !dishName || !comment) return;
  const review = {
    schema_version: 1,
    canteen: windowItem.canteen,
    window_id: windowItem.id,
    window: windowItem.window,
    goods_id: dish?.id ?? null,
    dish: dishName,
    meal: $("meal").value,
    rating: Number(document.querySelector('input[name="rating"]:checked').value),
    visit_date: $("visit-date").value,
    comment,
  };
  const filename = `reviews/${review.visit_date}-${crypto.randomUUID()}.json`;
  const body = JSON.stringify(review, null, 2) + "\n";
  $("review-filename").textContent = filename;
  $("review-json").value = body;
  $("prepared").hidden = false;
  $("prepared").scrollIntoView({ behavior: "smooth", block: "nearest" });
  const url = new URL(`${REPO}/new/main`);
  url.searchParams.set("filename", filename);
  url.searchParams.set("value", body);
  window.open(url.toString(), "_blank", "noopener,noreferrer");
});

$("copy-json").addEventListener("click", async () => {
  await navigator.clipboard.writeText($("review-json").value);
  $("copy-json").textContent = "已复制";
});

loadData();
