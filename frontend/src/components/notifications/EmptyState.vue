<script>
import { Bell } from 'lucide-vue-next';

export default {
    components: { Bell }
}
</script>

<template>
    <div class="empty-state">
        <div class="empty-icon">
            <Bell size="48" />
        </div>
        <p class="empty-text">{{ $t('notifications_page.empty_title') }}</p>
        <p class="empty-subtext">{{ $t('notifications_page.empty_subtitle') }}</p>
    </div>
</template>

<style scoped>
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding-top: 80px;
    text-align: center;
}

.empty-icon {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: var(--bg-surface);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    margin-bottom: 16px;
}

.empty-text {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.empty-subtext {
    font-size: 13px;
    color: var(--text-secondary);
}
</style>
