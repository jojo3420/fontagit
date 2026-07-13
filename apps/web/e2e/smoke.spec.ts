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
