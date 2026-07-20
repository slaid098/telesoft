<script lang="ts">
import Layout from "../routes/+layout.svelte";

const { data } = $props();
</script>

<Layout {data}>
  <div data-testid="child-stub">child</div>
</Layout>