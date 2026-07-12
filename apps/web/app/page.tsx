export default function Home() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-background text-foreground">
      <main className="flex flex-col items-center justify-center gap-4 text-center px-4">
        <h1 className="text-4xl font-bold text-brand">FontAgit</h1>
        <p className="text-lg text-neutral-600 dark:text-neutral-300">
          당신의 폰트 아지트 (초기 뼈대)
        </p>
      </main>
    </div>
  );
}
