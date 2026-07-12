export default function Home() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-background text-foreground">
      <main className="flex flex-col items-center justify-center gap-4 text-center px-4">
        <h1 className="text-4xl font-bold text-brand">FontAgit</h1>
        <p className="text-lg text-gray-600 dark:text-gray-400">
          Manage and organize your fonts with ease
        </p>
      </main>
    </div>
  );
}
