package com.hilariogrp.edepuerta;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** Envuelve la app web /puerta/ en una app Android: pantalla completa, camara y pantalla siempre encendida. */
public class MainActivity extends Activity {
    private static final int REQ_CAMARA = 77;
    private WebView web;
    private PermissionRequest pendiente;
    private String baseUrl;
    private String host;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        baseUrl = getString(R.string.base_url);
        host = Uri.parse(baseUrl).getHost();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(Color.parseColor("#0f172a"));
        getWindow().setNavigationBarColor(Color.parseColor("#0f172a"));

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0f172a"));
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);                  // localStorage: guarda el codigo de puerta
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                return !host.equalsIgnoreCase(r.getUrl().getHost());   // nunca sale del dominio
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) mostrarSinConexion();
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest req) {
                runOnUiThread(() -> {
                    boolean origenOk = host.equalsIgnoreCase(req.getOrigin().getHost());
                    boolean pideCamara = false;
                    for (String r : req.getResources()) {
                        if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r)) pideCamara = true;
                    }
                    if (!origenOk || !pideCamara) { req.deny(); return; }
                    if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                        req.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
                    } else {
                        pendiente = req;
                        requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMARA);
                    }
                });
            }
        });

        if (b == null) web.loadUrl(baseUrl); else web.restoreState(b);
    }

    private void mostrarSinConexion() {
        String html = "<body style=\"background:#0f172a;color:#f8fafc;font-family:sans-serif;text-align:center;padding:30% 24px 0\">"
                + "<div style=\"font-size:64px\">&#128225;</div><h2>Sin conexi&oacute;n</h2>"
                + "<p style=\"color:#94a3b8\">No se pudo abrir EDE Puerta. Revisa tu internet.</p>"
                + "<button onclick=\"location.href='" + baseUrl + "'\" style=\"font-size:18px;padding:14px 28px;border:0;border-radius:14px;background:#2563eb;color:#fff;font-weight:700\">Reintentar</button></body>";
        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        if (code != REQ_CAMARA || pendiente == null) return;
        if (res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED) {
            pendiente.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
        } else {
            pendiente.deny();
        }
        pendiente = null;
    }

    @Override
    public void onWindowFocusChanged(boolean f) {
        super.onWindowFocusChanged(f);
        if (f) {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        }
    }

    @Override protected void onSaveInstanceState(Bundle o) { super.onSaveInstanceState(o); web.saveState(o); }
    @Override protected void onPause() { web.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); }
    @Override public void onBackPressed() { moveTaskToBack(true); }   // no cierra la app por accidente
}
