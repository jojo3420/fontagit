import { test, expect } from '@playwright/test';

const routes = [
  { path: '/', name: 'Home' },
  { path: '/fonts', name: 'Fonts List' },
  { path: '/fonts/pretendard', name: 'Pretendard Detail' },
  { path: '/fonts/sandoll-gothic-neo', name: 'Sandoll Gothic Neo Detail' },
  { path: '/trends', name: 'Trends' },
  { path: '/playground', name: 'Playground' },
  { path: '/compare', name: 'Compare' },
  { path: '/collections', name: 'Collections' },
  { path: '/collections/dawn-serif', name: 'Collection Detail' },
  { path: '/submit', name: 'Submit' },
];

routes.forEach((route) => {
  test(`smoke: ${route.name} loads without console errors`, async ({
    page,
  }) => {
    const errors: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(`[${msg.type()}] ${msg.text()}`);
      }
    });

    await page.goto(route.path, { waitUntil: 'networkidle' });

    expect(errors).toEqual([]);
  });

  test(`smoke: ${route.name} captures screenshot (desktop/mobile)`, async ({
    page,
  }) => {
    await page.goto(route.path, { waitUntil: 'networkidle' });

    // Capture screenshot for desktop and mobile viewports
    await expect(page).toHaveScreenshot(`${route.name.replace(/\s+/g, '-').toLowerCase()}-screenshot.png`, {
      maxDiffPixels: 100,
    });
  });
});

test('smoke: 404 Page renders branded content', async ({ page }) => {
  await page.goto('/not-found', { waitUntil: 'networkidle' });

  // Assert branded 404 copy is visible
  await expect(page.getByText(/아지트 입구로 모실게요/)).toBeVisible();

  // Assert home button exists
  await expect(page.getByRole('link', { name: '홈으로 돌아가기' })).toBeVisible();
});

test('playground canvas updates all specimens live', async ({ page }) => {
  await page.goto('/playground/', { waitUntil: 'networkidle' });
  await page.getByLabel('캔버스 입력').fill('불꽃');
  await expect(page.getByText('불꽃').first()).toBeVisible();
});

test('playground preset fills the input', async ({ page }) => {
  await page.goto('/playground/', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: '당신의 폰트 아지트' }).click();
  await expect(page.getByLabel('캔버스 입력')).toHaveValue('당신의 폰트 아지트');
});

test('smoke: 404 Page captures screenshot (desktop/mobile)', async ({ page }) => {
  await page.goto('/not-found', { waitUntil: 'networkidle' });

  // Capture screenshot for desktop and mobile viewports
  await expect(page).toHaveScreenshot('404-page-screenshot.png', {
    maxDiffPixels: 100,
  });
});

test('preview input updates specimen live', async ({ page }) => {
  await page.goto('/fonts/pretendard/', { waitUntil: 'networkidle' });
  await page.getByLabel('미리보기 입력').fill('가나다 테스트');
  await expect(page.getByText('가나다 테스트').first()).toBeVisible();
});

test('compare updates all columns live and swaps a font', async ({ page }) => {
  await page.goto('/compare/', { waitUntil: 'networkidle' });
  await page.getByLabel('비교 문장 입력').fill('나란히');
  await expect(page.getByText('나란히').first()).toBeVisible();
  await page.getByLabel('2번 폰트 선택').selectOption('nanum-myeongjo');
  await expect(page.getByLabel('2번 폰트 선택')).toHaveValue('nanum-myeongjo');
});

test('header collections link navigates without 404', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.getByRole('navigation').getByRole('link', { name: '컬렉션' }).click();
  await expect(page).toHaveURL(/\/collections\/?$/);
  await expect(page.getByRole('heading', { name: '컬렉션', level: 1 })).toBeVisible();
});


test('submit form is a non-submitting mockup', async ({ page }) => {
  await page.goto('/submit/', { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: '폰트 등록 신청' })).toBeVisible();
  await page.getByRole('button', { name: '신청 보내기' }).click();
  await expect(page).toHaveURL(/\/submit\/?$/); // preventDefault로 제출/네비게이션 없음
});

test('mobile tab bar shows on small viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/', { waitUntil: 'networkidle' });
  await expect(page.getByRole('navigation', { name: '모바일 탭' })).toBeVisible();
});

test('mobile viewport shows compare tab in tab bar and hides header tool links', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/', { waitUntil: 'networkidle' });

  // Verify tab bar is visible and has 5 tabs
  const tabBar = page.getByRole('navigation', { name: '모바일 탭' });
  await expect(tabBar).toBeVisible();
  const tabLinks = tabBar.getByRole('link');
  await expect(tabLinks).toHaveCount(5);

  // Verify compare tab is visible with correct href
  await expect(tabBar.getByRole('link', { name: '비교' })).toBeVisible();
  await expect(tabBar.getByRole('link', { name: '비교' })).toHaveAttribute('href', /^\/compare\/?$/);

  // Verify header tool links (canvas and compare) are hidden on mobile
  const headerNav = page.getByRole('navigation').first();
  await expect(headerNav.getByRole('link', { name: '캔버스' })).toBeHidden();
  await expect(headerNav.getByRole('link', { name: '비교' })).toBeHidden();
});

test('theme toggle switches data-theme', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  const html = page.locator('html');
  const before = await html.getAttribute('data-theme');
  await page.getByLabel('다크모드 전환').click();
  const after = await html.getAttribute('data-theme');
  expect(after).not.toBe(before);
  expect(['light', 'dark']).toContain(after);
});

test('header nav contains canvas and compare links (desktop)', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/', { waitUntil: 'networkidle' });
  const nav = page.getByRole('navigation').first();
  await expect(nav.getByRole('link', { name: '캔버스' })).toBeVisible();
  await expect(nav.getByRole('link', { name: '캔버스' })).toHaveAttribute('href', /^\/playground\/?$/);
  await expect(nav.getByRole('link', { name: '비교' })).toBeVisible();
  await expect(nav.getByRole('link', { name: '비교' })).toHaveAttribute('href', /^\/compare\/?$/);
});
