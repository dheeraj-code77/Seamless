# Seamless Android release rules.

# Keep the zxing barcode scanner entry points reachable by reflection.
-keep class com.journeyapps.barcodescanner.** { *; }
-keep class com.google.zxing.** { *; }

# Keep the JavaScript bridge that the mobile web view talks to.
-keepclassmembers class com.seamless.app.MainActivity {
    @android.webkit.JavascriptInterface <methods>;
}
