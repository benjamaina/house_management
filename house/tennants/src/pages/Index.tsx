const Index = () => {
  // This component renders the HTML that can be copied for Django
  // The actual HTML string is displayed below for easy copying
  
  return (
    <div 
      dangerouslySetInnerHTML={{
        __html: `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>House Management System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #000000 0%, #1e3a8a 50%, #1d4ed8 100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }

        body::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(220, 241, 28, 0.05) 0%, transparent 50%);
            animation: pulse 8s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 0.5; }
            50% { transform: scale(1.1); opacity: 0.8; }
        }

        .container {
            position: relative;
            z-index: 1;
            text-align: center;
            max-width: 800px;
            width: 100%;
        }

        .logo-container {
            margin-bottom: 40px;
        }

        .logo {
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, #dcf11c 0%, #39e416 100%);
            border-radius: 24px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 20px 60px rgba(220, 241, 28, 0.3);
            transform: rotate(-5deg);
            transition: transform 0.3s ease;
        }

        .logo:hover {
            transform: rotate(0deg) scale(1.05);
        }

        .logo svg {
            width: 60px;
            height: 60px;
            fill: #000000;
        }

        h1 {
            font-size: 3.5rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 20px;
            text-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
            line-height: 1.2;
        }

        h1 span {
            background: linear-gradient(90deg, #dcf11c, #39e416);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .subtitle {
            font-size: 1.25rem;
            color: #93c5fd;
            margin-bottom: 50px;
            max-width: 500px;
            margin-left: auto;
            margin-right: auto;
            line-height: 1.6;
        }

        .buttons {
            display: flex;
            gap: 20px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 12px;
            padding: 18px 36px;
            font-size: 1.1rem;
            font-weight: 600;
            text-decoration: none;
            border-radius: 16px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s ease;
        }

        .btn:hover::before {
            left: 100%;
        }

        .btn-primary {
            background: linear-gradient(135deg, #dcf11c 0%, #39e416 100%);
            color: #000000;
            box-shadow: 0 10px 40px rgba(220, 241, 28, 0.4);
        }

        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 50px rgba(220, 241, 28, 0.5);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
            border: 2px solid rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
            border-color: rgba(255, 255, 255, 0.4);
            transform: translateY(-3px);
        }

        .btn svg {
            width: 24px;
            height: 24px;
        }

        .features {
            margin-top: 80px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 30px;
        }

        .feature {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }

        .feature:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-5px);
            border-color: rgba(220, 241, 28, 0.3);
        }

        .feature-icon {
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%);
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
        }

        .feature-icon svg {
            width: 28px;
            height: 28px;
            fill: #ffffff;
        }

        .feature h3 {
            color: #ffffff;
            font-size: 1.1rem;
            margin-bottom: 10px;
        }

        .feature p {
            color: #93c5fd;
            font-size: 0.9rem;
            line-height: 1.5;
        }

        .footer {
            margin-top: 60px;
            color: #60a5fa;
            font-size: 0.9rem;
        }

        @media (max-width: 768px) {
            h1 {
                font-size: 2.5rem;
            }
            
            .subtitle {
                font-size: 1rem;
            }
            
            .btn {
                padding: 15px 28px;
                font-size: 1rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo-container">
            <div class="logo">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 3L4 9v12h5v-7h6v7h5V9l-8-6z"/>
                </svg>
            </div>
        </div>
        
        <h1>Welcome to <span>House Management</span></h1>
        <p class="subtitle">Streamline your property management with our powerful and intuitive system. Manage tenants, track payments, and more.</p>
        
        <div class="buttons">
            <a href="/admin/" class="btn btn-primary">
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/>
                </svg>
                Admin Dashboard
            </a>
            <a href="/register/" class="btn btn-secondary">
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                </svg>
                Register Now
            </a>
        </div>

        <div class="features">
            <div class="feature">
                <div class="feature-icon">
                    <svg viewBox="0 0 24 24">
                        <path d="M12 3L4 9v12h16V9l-8-6zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 8.5 12 8.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5z"/>
                    </svg>
                </div>
                <h3>Property Tracking</h3>
                <p>Monitor all your properties in one central dashboard</p>
            </div>
            <div class="feature">
                <div class="feature-icon">
                    <svg viewBox="0 0 24 24">
                        <path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z"/>
                    </svg>
                </div>
                <h3>Payment Management</h3>
                <p>Track rent payments and generate financial reports</p>
            </div>
            <div class="feature">
                <div class="feature-icon">
                    <svg viewBox="0 0 24 24">
                        <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                    </svg>
                </div>
                <h3>Tenant Portal</h3>
                <p>Easy communication with tenants and service requests</p>
            </div>
        </div>

        <p class="footer">© 2024 House Management System. All rights reserved.</p>
    </div>
</body>
</html>
        `
      }}
    />
  );
};

export default Index;
