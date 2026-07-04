package app.route.notraffic;

import android.app.Notification;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Reads the phone's own incoming Viber notifications and stores messages
 * from the watched community groups, so the map can plot police checks /
 * accidents / alcohol tests reported there. Everything stays on-device.
 *
 * The user must grant "Notification access" to this app in Android Settings
 * (AndroidAlerts.openAccessSettings() opens that screen).
 */
public class AlertListener extends NotificationListenerService {

    static final String PKG_VIBER = "com.viber.voip";
    static final String PREFS = "alerts";
    static final String KEY_ITEMS = "items";
    static final String KEY_GROUPS = "groups";       // '|'-separated group names
    static final long MAX_AGE_MS = 6L * 3600 * 1000; // keep 6h of history
    static final int MAX_ITEMS = 150;

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        try {
            if (sbn == null || !PKG_VIBER.equals(sbn.getPackageName())) return;
            Notification n = sbn.getNotification();
            if (n == null || n.extras == null) return;
            Bundle ex = n.extras;

            CharSequence titleCs = ex.getCharSequence(Notification.EXTRA_TITLE);
            CharSequence textCs = ex.getCharSequence(Notification.EXTRA_TEXT);
            String title = titleCs == null ? "" : titleCs.toString().trim();
            String text = textCs == null ? "" : textCs.toString().trim();
            if (text.isEmpty()) return;

            SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);

            // Keep only the configured groups (match by name substring).
            String groups = sp.getString(KEY_GROUPS, "");
            if (!groups.isEmpty()) {
                boolean match = false;
                for (String g : groups.split("\\|")) {
                    g = g.trim();
                    if (!g.isEmpty() && title.toLowerCase().contains(g.toLowerCase())) {
                        match = true;
                        break;
                    }
                }
                if (!match) return;
            }

            JSONArray arr;
            try { arr = new JSONArray(sp.getString(KEY_ITEMS, "[]")); }
            catch (Exception e) { arr = new JSONArray(); }

            JSONObject o = new JSONObject();
            o.put("t", System.currentTimeMillis());
            o.put("g", title);
            o.put("m", text);
            arr.put(o);

            // Prune by age and cap the count.
            long now = System.currentTimeMillis();
            JSONArray keep = new JSONArray();
            int start = Math.max(0, arr.length() - MAX_ITEMS);
            for (int i = start; i < arr.length(); i++) {
                JSONObject it = arr.getJSONObject(i);
                if (now - it.optLong("t") <= MAX_AGE_MS) keep.put(it);
            }
            sp.edit().putString(KEY_ITEMS, keep.toString()).apply();
        } catch (Exception ignored) { }
    }
}
