package app.route.notraffic;

import android.accessibilityservice.AccessibilityService;
import android.content.SharedPreferences;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;

/**
 * Reads the open group chat directly from the screen (accessibility),
 * so it does NOT depend on notifications arriving — the biggest source
 * of misses on big communities. When the user opens a watched group,
 * every visible message line is captured into the same store the map
 * reads (SharedPreferences "alerts").
 *
 * Requires the user to enable this app under
 *   Settings → Accessibility → (installed services).
 */
public class ViberReader extends AccessibilityService {

    private long lastScan = 0;

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event == null) return;
        int t = event.getEventType();
        if (t != AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED
                && t != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
                && t != AccessibilityEvent.TYPE_VIEW_SCROLLED) return;

        // ΜΟΝΟ Viber στο προσκήνιο — αγνόησε κάθε άλλη εφαρμογή.
        CharSequence pkg = event.getPackageName();
        if (pkg == null || !"com.viber.voip".contentEquals(pkg)) return;

        long now = System.currentTimeMillis();
        if (now - lastScan < 700) return;            // throttle heavy scans
        lastScan = now;

        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return;
        try {
            ArrayList<String> texts = new ArrayList<>();
            collect(root, texts, 0);
            if (texts.isEmpty()) return;

            SharedPreferences sp = getSharedPreferences(AlertListener.PREFS, MODE_PRIVATE);
            String groups = sp.getString(AlertListener.KEY_GROUPS, "");

            // Only capture while a watched group is on screen.
            String matched = "";
            if (!groups.isEmpty()) {
                outer:
                for (String txt : texts) {
                    String n = AlertListener.norm(txt);
                    for (String g : groups.split("\\|")) {
                        String ng = AlertListener.norm(g.trim());
                        if (!ng.isEmpty() && n.contains(ng)) { matched = txt.trim(); break outer; }
                    }
                }
                if (matched.isEmpty()) return;       // some other chat/app
            }
            String title = matched.isEmpty() ? "Ομάδα" : matched;

            JSONArray arr;
            try { arr = new JSONArray(sp.getString(AlertListener.KEY_ITEMS, "[]")); }
            catch (Exception e) { arr = new JSONArray(); }

            boolean changed = false;
            for (String text : texts) {
                if (!isMessage(text)) continue;
                String ntext = AlertListener.norm(text);
                boolean dup = false;
                for (int i = 0; i < arr.length(); i++) {
                    if (AlertListener.norm(arr.getJSONObject(i).optString("m")).equals(ntext)) {
                        dup = true; break;
                    }
                }
                if (dup) continue;
                JSONObject o = new JSONObject();
                o.put("t", now);
                o.put("g", title);
                o.put("m", text.trim());
                arr.put(o);
                changed = true;
            }
            if (!changed) return;

            JSONArray keep = new JSONArray();
            int start = Math.max(0, arr.length() - AlertListener.MAX_ITEMS);
            for (int i = start; i < arr.length(); i++) {
                JSONObject it = arr.getJSONObject(i);
                if (now - it.optLong("t") <= AlertListener.MAX_AGE_MS) keep.put(it);
            }
            sp.edit().putString(AlertListener.KEY_ITEMS, keep.toString()).apply();
        } catch (Exception ignored) {
        } finally {
            try { root.recycle(); } catch (Exception ignored) { }
        }
    }

    /** Depth-limited walk collecting visible text. */
    private void collect(AccessibilityNodeInfo node, ArrayList<String> out, int depth) {
        if (node == null || depth > 40) return;
        CharSequence tx = node.getText();
        if (tx != null && tx.length() > 0) out.add(tx.toString());
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo c = node.getChild(i);
            if (c != null) { collect(c, out, depth + 1); c.recycle(); }
        }
    }

    /** Keep real message lines; drop chrome (timestamps, hints, names, noise). */
    private boolean isMessage(String text) {
        String s = text.trim();
        if (s.length() < 6) return false;                 // too short to be useful
        if (s.matches("\\d{1,2}:\\d{2}")) return false;   // a bare timestamp
        if (s.split("\\s+").length < 2) return false;     // a single word (name/button)
        String n = AlertListener.norm(s);
        if (n.startsWith("μηνυμα")) return false;         // the compose hint "Μήνυμα.."
        if (AlertListener.isNoise(n)) return false;
        return true;
    }

    @Override
    public void onInterrupt() { }
}
