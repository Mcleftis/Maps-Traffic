package app.route.notraffic;

import android.app.Notification;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.Normalizer;
import java.util.ArrayList;

/**
 * Reads the phone's own incoming Viber notifications and stores messages
 * from the watched community groups, so the map can plot police checks /
 * accidents / alcohol tests reported there. Everything stays on-device.
 *
 * Only notifications posted AFTER notification access is granted can be
 * seen — Android never exposes past notifications.
 */
public class AlertListener extends NotificationListenerService {

    static final String PKG_VIBER = "com.viber.voip";
    static final String PREFS = "alerts";
    static final String KEY_ITEMS = "items";
    static final String KEY_GROUPS = "groups";       // '|'-separated group names
    static final long MAX_AGE_MS = 6L * 3600 * 1000; // keep 6h of history
    static final int MAX_ITEMS = 200;

    /** Lowercase + strip Greek accents, so "Αλέρτ"/"αλερτ" etc. all match. */
    static String norm(String s) {
        if (s == null) return "";
        return Normalizer.normalize(s, Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "").toLowerCase();
    }

    /** Viber service/teaser notifications — not real group messages. */
    static boolean isNoise(String normText) {
        return normText.matches(".*(δειτε .{0,20}μηνυμα|ισως χασατε|νεα μηνυματα"
                + "|αναπαντητη|missed call|new message|σας καλει|calling"
                + "|εγινε μελος|joined|reacted|αντεδρασε).*");
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        try {
            if (sbn == null || !PKG_VIBER.equals(sbn.getPackageName())) return;
            Notification n = sbn.getNotification();
            if (n == null || n.extras == null) return;
            Bundle ex = n.extras;

            CharSequence titleCs = ex.getCharSequence(Notification.EXTRA_TITLE);
            String title = titleCs == null ? "" : titleCs.toString().trim();

            SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);

            // Keep only the configured groups (accent/case-insensitive match).
            String groups = sp.getString(KEY_GROUPS, "");
            if (!groups.isEmpty()) {
                boolean match = false;
                String nt = norm(title);
                for (String g : groups.split("\\|")) {
                    g = norm(g.trim());
                    if (!g.isEmpty() && nt.contains(g)) { match = true; break; }
                }
                if (!match) return;
            }

            // Collect every text this notification carries: plain text,
            // big text, and the stacked InboxStyle lines Viber uses when
            // several messages are grouped into one notification.
            ArrayList<String> texts = new ArrayList<>();
            CharSequence t1 = ex.getCharSequence(Notification.EXTRA_TEXT);
            CharSequence t2 = ex.getCharSequence(Notification.EXTRA_BIG_TEXT);
            if (t1 != null && t1.length() > 0) texts.add(t1.toString().trim());
            if (t2 != null && t2.length() > 0 && (t1 == null
                    || !t2.toString().equals(t1.toString())))
                texts.add(t2.toString().trim());
            CharSequence[] lines = ex.getCharSequenceArray(Notification.EXTRA_TEXT_LINES);
            if (lines != null) {
                for (CharSequence l : lines) {
                    if (l != null && l.length() > 0) texts.add(l.toString().trim());
                }
            }
            if (texts.isEmpty()) return;

            JSONArray arr;
            try { arr = new JSONArray(sp.getString(KEY_ITEMS, "[]")); }
            catch (Exception e) { arr = new JSONArray(); }

            long now = System.currentTimeMillis();
            for (String text : texts) {
                if (text.isEmpty()) continue;
                String ntext = norm(text);
                if (isNoise(ntext)) continue;  // teaser, όχι πραγματικό μήνυμα
                // Dedupe: Viber re-posts the same message in summary
                // notifications; skip if we already stored this exact text.
                boolean dup = false;
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject it = arr.getJSONObject(i);
                    if (norm(it.optString("m")).equals(ntext)) { dup = true; break; }
                }
                if (dup) continue;

                JSONObject o = new JSONObject();
                o.put("t", now);
                o.put("g", title);
                o.put("m", text);
                arr.put(o);
            }

            // Prune by age and cap the count.
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
