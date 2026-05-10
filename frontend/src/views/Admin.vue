<template>
    <div class="p-4">
        <div class="grid mb-4">
        <div v-for="(v, k) in stats" :key="k" class="col-4">
            <div class="surface-card p-4 shadow-1 border-round text-center">
                <div class="text-500 font-bold mb-2 uppercase">{{ k }}</div>
                <div class="text-900 text-4xl">{{ v }}</div>
            </div>
        </div>
        </div>
        <DataTable :value="logs" paginator :rows="5" class="surface-card shadow-1 border-round">
        <Column field="Timestamp" header="Time"></Column>
        <Column field="Event" header="Event"></Column>
        <Column field="Message" header="Details"></Column>
        </DataTable>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import axios from 'axios';
const stats = ref({}), logs = ref([]);
onMounted(async () => {
  const s = await axios.get("http://localhost:8000/admin/stats");
  const l = await axios.get("http://localhost:8000/admin/logs");
  stats.value = s.data; logs.value = l.data;
});
</script>