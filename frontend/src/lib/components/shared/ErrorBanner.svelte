<script lang="ts">
  let { message, onRetry }: { message: string; onRetry?: () => void } = $props();
</script>

<div class="rounded-lg border border-danger-light bg-danger-light px-4 py-3 text-sm text-danger-dark" role="alert">
  <p>{message}</p>
  {#if onRetry}
    <button onclick={onRetry} class="mt-2 font-medium underline hover:no-underline">
      Try again
    </button>
  {/if}
</div>
